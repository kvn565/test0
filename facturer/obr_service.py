# obr_service.py — VERSION FINALE (alignée doc OBR v0.5 - 11/10/2023)
# Login + addInvoice_confirm + AddStockMovement + synchro stock après succès

import requests
import logging
import time
import json
import urllib3
from decimal import Decimal

from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .models import Facture, FacturePendingOBR, LigneFacture
from stock.models import SortieStock, EntreeStock   # ← Ajout nécessaire
from stock.obr_service import envoyer_entree_stock, envoyer_sortie_stock



logger = logging.getLogger(__name__)

# ─── CONFIGURATION ─────────────────────────────────────────────────────────
OBR_BASE_URL = "https://ebms.obr.gov.bi:9443/ebms_api"
TIMEOUT = 45
MAX_RETRIES = 5
BASE_RETRY_DELAY = 8

CACHE_TOKEN_KEY_TEMPLATE = "obr_token_{societe_pk}"
CACHE_TOKEN_TIMEOUT = 2700  # 45 min

# IMPORTANT : passez à True en production + certificat valide
VERIFY_CERT = not settings.DEBUG
if not VERIFY_CERT:
    logger.warning("⚠️ VERIFY_CERT désactivé → uniquement pour développement !")

ENDPOINT_LOGIN          = "/login/"
ENDPOINT_ADD_INVOICE    = "/addInvoice_confirm/"
ENDPOINT_CANCEL_INVOICE  = "/cancelInvoice/"
ENDPOINT_ADD_STOCK_MOVE = "/AddStockMovement/"


# ─── TOKEN ─────────────────────────────────────────────────────────────────
def get_obr_token(societe):
    """
    Récupère le token OBR pour une société, avec mise en cache.
    """
    cache_key = CACHE_TOKEN_KEY_TEMPLATE.format(societe_pk=societe.pk)
    token = cache.get(cache_key)
    if token:
        return token

    # Vérifie que les identifiants existent
    if not societe.obr_username or not societe.obr_password:
        raise ValueError(f"Identifiants OBR manquants pour {societe.nom}")

    # Prépare la requête
    url = f"{OBR_BASE_URL}{ENDPOINT_LOGIN}"
    payload = {
        "username": societe.obr_username,
        "password": societe.obr_password
    }

    # Envoi de la requête
    resp = requests.post(url, json=payload, timeout=TIMEOUT, verify=VERIFY_CERT)
    resp.raise_for_status()
    data = resp.json()

    # Vérifie la réponse
    if not data.get("success"):
        raise ValueError(f"Login OBR échoué : {data.get('msg')}")

    # Récupère le token et le met en cache
    token = data["result"]["token"]
    cache.set(cache_key, token, CACHE_TOKEN_TIMEOUT)
    return token

def get_obr_headers(societe):
    return {
        "Authorization": f"Bearer {get_obr_token(societe)}",
        "Content-Type": "application/json"
    }


# ─── PAYLOAD FACTURE ───────────────────────────────────────────────────────
def build_invoice_payload(facture):
    societe = facture.societe
    client  = facture.client
    lignes  = facture.lignes.select_related('produit', 'service').all()

    # Format date + heure
    datetime_str = f"{facture.date_facture.strftime('%Y-%m-%d')} {facture.heure_facture.strftime('%H:%M:%S')}"

    # Mapping mode paiement
    payment_mapping = {'CAISSE': '1', 'BANQUE': '2', 'CREDIT': '3', 'AUTRES': '4'}
    payment_type_obr = payment_mapping.get(facture.mode_paiement, '1')

    payload = {
        "invoice_number": str(facture.numero_obr)[:30],
        "invoice_date": datetime_str,
        "invoice_type": str(facture.type_facture)[:2],
        "tp_type": str(getattr(societe, 'tp_type', '2'))[:2],
        "tp_name": str(getattr(societe, 'nom', ''))[:100],
        "tp_TIN": str(getattr(societe, 'nif', ''))[:30],
        "tp_trade_number": str(getattr(societe, 'registre_commerce', ''))[:20],
        "tp_postal_number": str(getattr(societe, 'boite_postale', ''))[:20],
        "tp_phone_number": str(getattr(societe, 'telephone', ''))[:20],
        "tp_address_province": str(getattr(societe, 'province', ''))[:50],
        "tp_address_commune": str(getattr(societe, 'commune', ''))[:50],
        "tp_address_quartier": str(getattr(societe, 'quartier', ''))[:50],
        "tp_address_avenue": str(getattr(societe, 'avenue', ''))[:50],
        "tp_address_rue": str(getattr(societe, 'rue', ''))[:50],
        "tp_address_number": str(getattr(societe, 'numero', ''))[:10],
        "vat_taxpayer": "1" if getattr(societe, 'assujeti_tva', False) else "0",
        "ct_taxpayer": "0",
        "tl_taxpayer": "0",
        "tp_fiscal_center": str(getattr(societe, 'centre_fiscal', 'DGC'))[:20],
        "tp_activity_sector": str(getattr(societe, 'secteur_activite', 'SERVICE MARCHAND'))[:250],
        "tp_legal_form": str(getattr(societe, 'forme_juridique', 'SARL'))[:50],
        "payment_type": payment_type_obr,
        "invoice_currency": str(getattr(facture, 'devise', 'BIF'))[:5],
        "customer_name": client.nom,
        "customer_TIN": getattr(client, 'nif', ''),
        "customer_address": str(getattr(client, 'adresse_complete', ''))[:100],
        "vat_customer_payer": "1" if getattr(client, 'assujetti_tva', False) else "0",
        "cancelled_invoice_ref": "",
        "invoice_ref": "",
        "cn_motif": "",
        "invoice_identifier": str(facture.invoice_identifier)[:150],
        "invoice_items": []
    }

    # Référence pour FA/RC
    if facture.type_facture in ['FA', 'RC'] and facture.facture_originale:
        payload["invoice_ref"] = facture.facture_originale.numero[:30]
        payload["cn_motif"] = facture.motif_avoir[:500] if facture.motif_avoir else "Avoir / Annulation"

    # Lignes — champs obligatoires + taxes conditionnelles
    for ligne in lignes:
        prix_ht  = float(ligne.prix_ht)
        quantite = float(ligne.quantite)
        montant_ht  = round(prix_ht * quantite, 2)
        montant_tva = round(montant_ht * float(ligne.taux_tva) / 100, 2)
        montant_ttc = round(montant_ht + montant_tva, 2)

        payload["invoice_items"].append({
            "item_designation": str(ligne.designation)[:500],
            "item_quantity": str(quantite),
            "item_price": str(prix_ht),
            "item_ct": str(getattr(ligne, 'ct', 0)),
            "item_tl": str(getattr(ligne, 'tl', 0)),
            "item_ott_tax": str(getattr(ligne, 'ott_tax', 0)),
            "item_tsce_tax": str(getattr(ligne, 'tsce_tax', 0)),
            "item_price_nvat": str(montant_ht),
            "vat": str(montant_tva),
            "item_price_wvat": str(montant_ttc),
            "item_total_amount": str(montant_ttc),
        })

    return payload


def envoyer_facture_obr(facture):
    """Envoie la facture à l'OBR + synchronise les mouvements de stock existants (sans recréation)"""
    societe = facture.societe
    pending, _ = FacturePendingOBR.objects.get_or_create(facture=facture)
    pending.retry_count = (pending.retry_count or 0) + 1
    pending.save(update_fields=['retry_count'])

    try:
        payload = build_invoice_payload(facture)

        logger.info(f"[OBR] Début envoi facture {facture.numero} | Type: {facture.type_facture}")

        url = f"{OBR_BASE_URL}{ENDPOINT_ADD_INVOICE}"

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = requests.post(
                    url,
                    json=payload,
                    headers=get_obr_headers(societe),
                    timeout=TIMEOUT,
                    verify=VERIFY_CERT
                )

                if resp.status_code in (401, 403):
                    logger.warning("Token invalide → refresh")
                    cache.delete(CACHE_TOKEN_KEY_TEMPLATE.format(societe_pk=societe.pk))
                    continue

                if resp.status_code == 200:
                    data = resp.json()

                    if data.get("success"):
                        # Mise à jour facture
                        facture.statut_obr = "ENVOYE"
                        facture.message_obr = data.get("msg", "Succès")
                        facture.date_envoi_obr = timezone.now()
                        facture.obr_registered_number = data.get("result", {}).get("invoice_registered_number", "")
                        facture.electronic_signature = data.get("electronic_signature", "")
                        facture.save()

                        pending.statut = "SUCCESS"
                        pending.message = data.get("msg", "OK")
                        pending.save()

                        # ====================== SYNCHRO STOCK (sans duplication) ======================
                        try:
                            if facture.type_facture == 'FN':
                                # Mise à jour des sorties SN existantes
                                sorties = SortieStock.objects.filter(
                                    facture=facture,
                                    statut_obr='EN_ATTENTE'
                                ).select_related('entree_stock', 'entree_stock__produit')

                                for sortie in sorties:
                                    result = envoyer_sortie_stock(sortie)
                                    success = result[0] if isinstance(result, tuple) else result.get('success', False)
                                    msg = result[1] if isinstance(result, tuple) else result.get('message', '')

                                    if success:
                                        sortie.statut_obr = 'ENVOYE'
                                        sortie.message_obr = msg or 'Envoyé avec succès'
                                        sortie.save(update_fields=['statut_obr', 'message_obr'])
                                    else:
                                        sortie.statut_obr = 'ECHEC'
                                        sortie.message_obr = msg or 'Échec envoi'
                                        sortie.save(update_fields=['statut_obr', 'message_obr'])

                            elif facture.type_facture == 'FA':
                                # Mise à jour des entrées ER existantes (celles créées dans ajuster_stock)
                                traiter_stock_pour_avoir(facture)

                        except Exception as stock_err:
                            logger.warning(f"Facture envoyée mais erreur synchro stock: {stock_err}", exc_info=True)

                        return {'success': True, 'message': data.get("msg", "Facture envoyée avec succès")}

                # Gestion erreur
                data = resp.json() if resp.headers.get('content-type', '').startswith('application/json') else {}
                msg = data.get("msg") or f"Erreur HTTP {resp.status_code}"
                logger.warning(f"[OBR] Échec tentative {attempt}: {msg}")
                pending.message = msg
                pending.save(update_fields=['message'])

            except requests.RequestException as e:
                msg = f"Tentative {attempt} - Erreur réseau: {str(e)}"
                logger.error(msg)
                pending.message = msg
                pending.save(update_fields=['message'])
                time.sleep(BASE_RETRY_DELAY)

        pending.statut = "FAILED"
        pending.save()
        return {'success': False, 'message': f"Échec après {MAX_RETRIES} tentatives"}

    except Exception as e:
        logger.exception(f"[OBR] Erreur critique facture {facture.numero}")
        pending.statut = "FAILED"
        pending.message = str(e)
        pending.save()
        return {'success': False, 'message': str(e)}


@transaction.atomic
def traiter_stock_pour_avoir(facture):
    """Met à jour et envoie les entrées ER existantes pour les factures d'avoir (FA)"""
    if facture.type_facture != 'FA':
        return

    logger.info(f"[STOCK] Traitement avoir FA {facture.numero}")

    # On récupère les entrées ER déjà créées dans ajuster_stock (pas de recréation !)
    entrees = EntreeStock.objects.filter(
        facture=facture,
        type_entree='ER',
        statut_obr='EN_ATTENTE'
    ).select_related('produit')

    for entree in entrees:
        try:
            result = envoyer_entree_stock(entree)

            success = result[0] if isinstance(result, tuple) else result.get('success', False)
            msg = result[1] if isinstance(result, tuple) else result.get('message', '')

            if success:
                entree.statut_obr = 'ENVOYE'
                entree.message_obr = msg or 'Envoyé avec succès à l\'OBR'
                entree.save(update_fields=['statut_obr', 'message_obr'])
                logger.info(f"[STOCK] Entrée ER #{entree.pk} → ENVOYE")
            else:
                entree.statut_obr = 'ECHEC'
                entree.message_obr = msg or 'Échec envoi'
                entree.save(update_fields=['statut_obr', 'message_obr'])
                logger.warning(f"[STOCK] Entrée ER #{entree.pk} → ECHEC : {msg}")

        except Exception as e:
            logger.error(f"[STOCK] Erreur sur entrée ER {entree.pk}: {e}", exc_info=True)
            entree.statut_obr = 'ECHEC'
            entree.message_obr = str(e)[:500]
            entree.save(update_fields=['statut_obr', 'message_obr'])
            
# ─── VUE AJAX (appel frontend) ─────────────────────────────────────────────
@login_required
@require_POST
def ajax_envoyer_obr(request, pk):
    """Envoi de la facture à l'OBR"""
    facture = get_object_or_404(Facture, pk=pk, societe=request.user.societe)

    if facture.statut_obr != 'EN_ATTENTE':
        return JsonResponse({
            'ok': False, 
            'error': f"Statut actuel : {facture.get_statut_obr_display()}"
        }, status=400)

    if facture.lignes.count() == 0:
        return JsonResponse({'ok': False, 'error': 'Facture vide'}, status=400)

    try:
        result = envoyer_facture_obr(facture)
        
        return JsonResponse({
            'ok': True,
            'message': result.get('message', 'Facture envoyée avec succès à l’OBR'),
            'signature': facture.electronic_signature,
            'registered_number': facture.obr_registered_number,
            'date_envoi': facture.date_envoi_obr.isoformat() if facture.date_envoi_obr else None,
        })
    except ValueError as ve:
        return JsonResponse({'ok': False, 'error': str(ve)}, status=400)
    except Exception as e:
        logger.exception(f"Erreur envoi OBR facture {pk}")
        return JsonResponse({'ok': False, 'error': 'Erreur serveur'}, status=500)



# ─── ANNULATION FACTURE ────────────────────────────────────────────────────

# ─── ANNULATION FACTURE (alignée doc OBR v0.5) ────────────────────────────────────────────────────

def annuler_facture_obr(facture, motif: str):
    """
    Version corrigée :
    - Toujours retourne {success, message}
    - API appelée hors transaction
    - Mise à jour DB sécurisée
    """

    if not motif or not motif.strip():
        return {'success': False, 'message': "Motif obligatoire"}

    motif = motif.strip()[:500]
    societe = facture.societe

    try:
        message_obr = ""

        # ================= API OBR =================
        if facture.statut_obr == 'ENVOYE':

            if not facture.invoice_identifier:
                return {'success': False, 'message': "invoice_identifier manquant"}

            payload = {
                "invoice_identifier": facture.invoice_identifier,
                "cn_motif": motif
            }

            url = f"{OBR_BASE_URL}{ENDPOINT_CANCEL_INVOICE}"

            resp = requests.post(
                url,
                json=payload,
                headers=get_obr_headers(societe),
                timeout=TIMEOUT,
                verify=VERIFY_CERT
            )

            if resp.status_code != 200:
                try:
                    data = resp.json()
                    msg = data.get("msg", f"HTTP {resp.status_code}")
                except:
                    msg = resp.text[:300]

                return {'success': False, 'message': msg}

            data = resp.json()

            if not data.get("success"):
                return {'success': False, 'message': data.get("msg", "Refus OBR")}

            message_obr = data.get("msg", "Annulation OBR réussie")

        else:
            message_obr = f"Annulée localement - Motif : {motif}"

        # ================= DATABASE =================
        with transaction.atomic():

            pending, _ = FacturePendingOBR.objects.get_or_create(facture=facture)

            facture.statut_obr = 'ANNULE'
            facture.message_obr = message_obr
            facture.motif_avoir = f"Annulation : {motif}"
            facture.date_annulation = timezone.now()   # ✅ AJOUT IMPORTANT

            facture.save(update_fields=[
                'statut_obr',
                'message_obr',
                'motif_avoir',
                'date_annulation'
            ])

            pending.statut = "SUCCESS"
            pending.message = message_obr
            pending.save(update_fields=['statut', 'message'])

        return {'success': True, 'message': message_obr}

    except Exception as e:
        logger.exception(f"[OBR Cancel] Erreur facture {facture.numero}")

        try:
            pending, _ = FacturePendingOBR.objects.get_or_create(facture=facture)
            pending.statut = "FAILED"
            pending.message = str(e)[:500]
            pending.save(update_fields=['statut', 'message'])
        except:
            pass

        return {'success': False, 'message': str(e)}

# ─── NETTOYAGE DES DOUBLONS (à utiliser une seule fois) ─────────────────────
def nettoyer_doublons_stock():
    """
    Met à jour toutes les sorties stock qui causent des erreurs 409 
    pour qu'elles ne soient plus réessayées.
    À appeler une seule fois manuellement.
    """
    from stock.models import SortieStock

    updated = SortieStock.objects.filter(
        statut_obr='ECHEC',
        message_obr__icontains='409'
    ).update(
        statut_obr='NON_CONCERNE',
        message_obr='Doublon déjà enregistré à l\'OBR - Ignoré'
    )

    logger.info(f"Nettoyage terminé : {updated} sorties marquées comme NON_CONCERNE (409)")
    print(f"✅ {updated} sorties en doublon ont été nettoyées.")

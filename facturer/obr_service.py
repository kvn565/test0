# obr_service.py — VERSION FINALE (alignée doc OBR v0.5 - 11/10/2023)
# Login + addInvoice_confirm + AddStockMovement + synchro stock après succès

import requests
import logging
import time
import json
import urllib3
from decimal import Decimal, ROUND_DOWN

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


# ─── URL OBR ───────────────────────────────────────────────────────────────
def get_obr_base_url(societe):
    from urllib.parse import urlparse
    port = 8443 if getattr(societe, 'obr_mode_production', False) else 9443
    url = getattr(societe, 'obr_base_url', None)
    if url and str(url).strip():
        parsed = urlparse(str(url).strip())
        host = parsed.hostname or "ebms.obr.gov.bi"
        path = parsed.path.rstrip('/') or "/ebms_api"
        return f"{parsed.scheme}://{host}:{port}{path}"
    return f"https://ebms.obr.gov.bi:{port}/ebms_api"


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
    url = f"{get_obr_base_url(societe)}{ENDPOINT_LOGIN}"
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
    lignes  = facture.lignes.select_related('produit', 'service', 'taux_tva').all()

    # Date/heure extraite de l'identifiant (régénéré juste avant dans envoyer_facture_obr)
    ident = facture.invoice_identifier
    date_part = ident.split('/')[2]  # YYYYMMDDHHMMSS
    datetime_str = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]} {date_part[8:10]}:{date_part[10:12]}:{date_part[12:14]}"

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
        # Utiliser les montants déjà calculés par le modèle (formule unique)
        prix_ht    = float(ligne.prix_unitaire_ht)
        quantite   = float(ligne.quantite)
        taux       = float(ligne.taux_tva_valeur)
        montant_ht = ligne.montant_ht
        montant_tva = (montant_ht * Decimal(str(taux)) / Decimal('100')).quantize(Decimal('0.001'), rounding=ROUND_DOWN)
        montant_ttc = (montant_ht + montant_tva).quantize(Decimal('0.001'), rounding=ROUND_DOWN)

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
        # Régénérer l'identifiant avec la date/heure de l'envoi
        facture.generate_invoice_identifier()
        facture.save(update_fields=['invoice_identifier'])
        facture.refresh_from_db()

        payload = build_invoice_payload(facture)

        logger.info(f"[OBR] Début envoi facture {facture.numero} | Type: {facture.type_facture}")

        url = f"{get_obr_base_url(societe)}{ENDPOINT_ADD_INVOICE}"

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
                        raw_date = data.get("result", {}).get("invoice_registered_date", "")
                        if raw_date:
                            from datetime import datetime as dt_lib
                            try:
                                facture.obr_registered_date = dt_lib.strptime(raw_date, "%Y-%m-%d %H:%M:%S")
                            except (ValueError, TypeError):
                                pass
                        facture.obr_mode_envoye = societe.obr_mode_production
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
    mode_production = request.user.societe.obr_mode_production
    facture = get_object_or_404(Facture, pk=pk, societe=request.user.societe, obr_mode_envoye=mode_production)

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

@transaction.atomic
def annuler_facture_obr(facture, motif: str):
    """
    Annule une facture selon les règles OBR.
    - Si ENVOYE → appel réel à cancelInvoice
    - Si EN_ATTENTE ou ECHEC → annulation locale uniquement
    """
    if not motif or not motif.strip():
        raise ValueError("Le motif d'annulation est obligatoire.")

    motif = motif.strip()[:500]
    societe = facture.societe
    pending, _ = FacturePendingOBR.objects.get_or_create(facture=facture)

    # Mise à jour du motif (réutilisation du champ existant)
    facture.motif_avoir = f"Annulation : {motif}"

    try:
        if facture.statut_obr == 'ENVOYE':
            # === CAS 1 : Facture déjà envoyée → appel API OBR ===
            if not facture.invoice_identifier:
                raise ValueError("invoice_identifier manquant pour annulation OBR.")

            payload = {
                "invoice_identifier": facture.invoice_identifier,
                "cn_motif": motif
            }

            url = f"{get_obr_base_url(societe)}{ENDPOINT_CANCEL_INVOICE}"

            logger.info(f"[OBR Cancel] Tentative annulation facture {facture.numero} (ENVOYE)")

            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    headers = get_obr_headers(societe)
                    resp = requests.post(
                        url, json=payload, headers=headers,
                        timeout=TIMEOUT, verify=VERIFY_CERT
                    )

                    # Token expiré → refresh et réessai
                    if resp.status_code in (401, 403):
                        logger.warning(f"[OBR Cancel] Token invalide (tentative {attempt}) → refresh")
                        cache.delete(CACHE_TOKEN_KEY_TEMPLATE.format(societe_pk=societe.pk))
                        if attempt == MAX_RETRIES:
                            raise ValueError("Token OBR invalide après plusieurs tentatives de rafraîchissement")
                        continue

                    if resp.status_code != 200:
                        try:
                            data = resp.json()
                            error_msg = data.get("msg", f"HTTP {resp.status_code}")
                        except Exception:
                            error_msg = resp.text[:300]
                        raise ValueError(f"Échec OBR : {error_msg}")

                    data = resp.json()

                    if not data.get("success"):
                        raise ValueError(data.get("msg") or "Annulation refusée par l'OBR")

                    facture.message_obr = "✓ OBR : " + (data.get("msg", "") or resp.text[:500])
                    logger.info(f"[OBR Cancel] Succès pour facture {facture.numero}")
                    break

                except requests.RequestException as e:
                    msg = f"Tentative {attempt} - Erreur réseau: {str(e)}"
                    logger.error(msg)
                    if attempt < MAX_RETRIES:
                        time.sleep(BASE_RETRY_DELAY)
                    else:
                        raise ValueError(msg)

        else:
            # === CAS 2 : Facture EN_ATTENTE ou ECHEC → annulation locale ===
            facture.message_obr = f"Annulée localement avant envoi - Motif : {motif}"

            logger.info(f"[OBR Cancel] Annulation locale pour facture {facture.numero} (statut: {facture.statut_obr})")

        # Mise à jour commune
        facture.statut_obr = 'ANNULE'
        facture.save(update_fields=['statut_obr', 'message_obr', 'motif_avoir'])

        # ====================== RESTAURATION STOCK AVEC SYNCHRO OBR ======================
        from stock.obr_service import envoyer_entree_stock, envoyer_sortie_stock

        if facture.type_facture == 'FN':
            for ligne in facture.lignes.filter(produit__isnull=False).select_related('produit'):
                entree = EntreeStock.objects.create(
                    societe=societe, produit=ligne.produit, facture=facture,
                    type_entree='ER', date_entree=timezone.now().date(),
                    quantite=ligne.quantite, prix_revient=Decimal('0'),
                    prix_vente_actuel=ligne.prix_vente_tvac or 0,
                    numero_ref=f"ANNUL-FN-{facture.numero}",
                    commentaire=f"Restauration stock après annulation facture {facture.numero}",
                    statut_obr='EN_ATTENTE', fournisseur=None,
                )
                try:
                    result = envoyer_entree_stock(entree)
                    success = result[0] if isinstance(result, (list, tuple)) else result.get('success', False)
                    msg = result[1] if isinstance(result, (list, tuple)) else result.get('message', '')
                    if not success:
                        logger.warning(f"Échec envoi OBR stock ({msg}) - Restauration locale")
                        EntreeStock.objects.filter(pk=entree.pk).delete()
                        EntreeStock.objects.create(
                            societe=societe, produit=ligne.produit, facture=facture,
                            type_entree='ER', date_entree=timezone.now().date(),
                            quantite=ligne.quantite, prix_revient=Decimal('0'),
                            prix_vente_actuel=ligne.prix_vente_tvac or 0,
                            numero_ref=f"ANNUL-FN-{facture.numero}",
                            commentaire=f"Restauration locale (échec OBR) facture {facture.numero}",
                            statut_obr='ENVOYE', fournisseur=None,
                        )
                except Exception as stock_err:
                    logger.warning(f"Exception envoi OBR stock: {stock_err}")

        elif facture.type_facture == 'FA':
            for ligne in facture.lignes.filter(produit__isnull=False).select_related('produit'):
                entree_ref = ligne.produit.entrees_stock.filter(societe=societe).first()
                if not entree_ref:
                    continue
                sortie = SortieStock.objects.create(
                    societe=societe, type_sortie='SN', entree_stock=entree_ref,
                    quantite=ligne.quantite, prix=ligne.prix_vente_tvac or 0,
                    date_sortie=timezone.now().date(), code=f"REV-FA-{facture.numero}",
                    commentaire=f"Révocation retour après annulation avoir {facture.numero}",
                    statut_obr='EN_ATTENTE', facture=facture,
                )
                try:
                    result = envoyer_sortie_stock(sortie)
                    success = result[0] if isinstance(result, (list, tuple)) else result.get('success', False)
                    msg = result[1] if isinstance(result, (list, tuple)) else result.get('message', '')
                    if not success:
                        logger.warning(f"Échec envoi OBR sortie ({msg}) - Restauration locale")
                        SortieStock.objects.filter(pk=sortie.pk).delete()
                        entree_ref2 = ligne.produit.entrees_stock.filter(societe=societe).first()
                        if entree_ref2:
                            SortieStock.objects.create(
                                societe=societe, type_sortie='SN', entree_stock=entree_ref2,
                                quantite=ligne.quantite, prix=ligne.prix_vente_tvac or 0,
                                date_sortie=timezone.now().date(), code=f"REV-FA-{facture.numero}",
                                commentaire=f"Révocation locale (échec OBR) avoir {facture.numero}",
                                statut_obr='ENVOYE', facture=facture,
                            )
                except Exception as stock_err:
                    logger.warning(f"Exception envoi OBR sortie: {stock_err}")

        pending.statut = "SUCCESS"
        pending.message = "Annulée avec succès"
        pending.save(update_fields=['statut', 'message'])

        return {'success': True, 'message': facture.message_obr}

    except Exception as e:
        logger.exception(f"[OBR Cancel] Erreur annulation facture {facture.numero}")
        pending.statut = "FAILED"
        pending.message = str(e)[:500]
        pending.save(update_fields=['statut', 'message'])
        raise


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

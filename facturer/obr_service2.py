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

from .models import Facture, FacturePendingOBR, LigneFacture

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
    """Envoie une facture à l'OBR - Version finale propre"""
    societe = facture.societe
    pending, _ = FacturePendingOBR.objects.get_or_create(facture=facture)
    pending.retry_count = (pending.retry_count or 0) + 1
    pending.save(update_fields=['retry_count'])

    try:
        token = get_obr_token(societe)
        payload = build_invoice_payload(facture)

        logger.info(f"[OBR] Envoi facture {facture.numero}")
        url = OBR_BASE_URL + ENDPOINT_ADD_INVOICE

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = requests.post(
                    url,
                    json=payload,
                    headers=get_obr_headers(societe),
                    timeout=TIMEOUT,
                    verify=VERIFY_CERT
                )

                logger.info(f"[OBR] Tentative {attempt} → HTTP {resp.status_code}")

                if resp.status_code in (401, 403):
                    logger.warning("Token invalide → refresh")
                    cache.delete(CACHE_TOKEN_KEY_TEMPLATE.format(societe_pk=societe.pk))
                    token = get_obr_token(societe)
                    continue

                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("success"):
                        # Mise à jour correcte de la facture
                        facture.statut_obr = "ENVOYE"
                        facture.message_obr = data.get("msg", "Succès")
                        facture.date_envoi_obr = timezone.now()
                        facture.obr_registered_number = data.get("result", {}).get("invoice_registered_number", "")
                        facture.electronic_signature = data.get("electronic_signature", "") or \
                                                       data.get("result", {}).get("electronic_signature", "")
                        facture.save()

                        pending.statut = "SUCCESS"
                        pending.message = data.get("msg", "OK")
                        pending.save()

                        # === GESTION STOCK SELON DOCUMENTATION OBR ===
                        try:
                            if facture.type_facture == 'FN':
                                # Facture Normale → Sortie de stock (SN)
                                envoyer_mouvements_stock_en_attente(societe=societe)
                                logger.info(f"[STOCK] Sorties SN envoyées après FN {facture.numero}")

                            elif facture.type_facture == 'FA':
                                # Facture Avoir → Entrée Retour marchandise (ER)
                                traiter_stock_pour_avoir(facture)
                                logger.info(f"[STOCK] Entrées ER créées pour avoir FA {facture.numero}")

                        except Exception as stock_e:
                            logger.warning(f"Facture envoyée à OBR mais erreur gestion stock : {stock_e}")

                        return {'success': True, 'message': data.get("msg", "Envoyée avec succès")}

                # Gestion des erreurs
                try:
                    data = resp.json()
                    msg = data.get("msg") or f"Erreur {resp.status_code}"
                except Exception:
                    msg = f"Erreur {resp.status_code} - réponse non JSON"

                logger.warning(f"[OBR] Échec tentative {attempt}: {msg}")
                pending.message = msg
                pending.save(update_fields=['message'])

            except requests.RequestException as e:
                msg = f"Tentative {attempt} - Erreur réseau : {str(e)}"
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
    """
    Crée + envoie immédiatement les entrées ER vers l'OBR
    """
    if facture.type_facture != 'FA':
        return

    for ligne in facture.lignes.filter(produit__isnull=False).select_related('produit'):
        produit = ligne.produit
        try:
            # 1. Création locale de l'entrée
            entree = EntreeStock.objects.create(
                societe=facture.societe,
                type_entree='ER',
                produit=produit,
                fournisseur=None,
                quantite=ligne.quantite,
                prix_revient=Decimal(str(produit.prix_vente or 0)),
                prix_vente_actuel=Decimal(str(produit.prix_vente_tvac or 0)),
                date_entree=facture.date_facture,
                statut_obr='EN_ATTENTE',
                numero_ref=f"RET-FA-{facture.numero or 'N/A'}",
                commentaire=f"Retour via avoir {facture.numero} - Client: {facture.client.nom if facture.client else ''}",
                facture=facture,
            )

            # 2. Envoi immédiat à l'OBR
            success = envoyer_mouvement_stock_er(entree, facture)

            if success:
                entree.statut_obr = 'ENVOYE'
                entree.date_envoi_obr = timezone.now()
                entree.save(update_fields=['statut_obr', 'date_envoi_obr'])
                logger.info(f"[STOCK] Entrée ER envoyée avec succès pour produit {produit.designation}")
            else:
                logger.warning(f"[STOCK] Entrée ER créée mais échec envoi OBR pour produit {produit.designation}")

        except Exception as e:
            logger.error(f"[STOCK] Erreur traitement ER ligne {ligne.pk}: {e}")
# ─── VUE AJAX (appel frontend) ─────────────────────────────────────────────

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


def envoyer_mouvement_stock_er(entree, facture):
    """Envoie un mouvement de type ER (retour) à l'OBR"""
    societe = entree.societe
    try:
        headers = get_obr_headers(societe)
        url = f"{OBR_BASE_URL}{ENDPOINT_ADD_STOCK_MOVE}"

        payload = {
            "system_or_device_id": str(societe.obr_system_id or "").strip(),
            "item_code": getattr(entree.produit, 'code', f"PROD-{entree.produit.pk}")[:30],
            "item_designation": entree.produit.designation[:500],
            "item_quantity": float(entree.quantite),
            "item_measurement_unit": getattr(entree.produit, 'unite', 'unité')[:20],
            "item_cost_price": float(entree.prix_revient or 0),
            "item_cost_price_currency": getattr(facture, 'devise', 'BIF'),
            "item_movement_type": "ER",
            "item_movement_invoice_ref": facture.invoice_identifier or facture.numero_obr,
            "item_movement_description": entree.commentaire or f"Retour avoir {facture.numero}",
            "item_movement_date": f"{entree.date_entree.strftime('%Y-%m-%d')} {facture.heure_facture.strftime('%H:%M:%S') if hasattr(facture, 'heure_facture') else '12:00:00'}"
        }

        resp = requests.post(url, json=payload, headers=headers, timeout=30, verify=VERIFY_CERT)

        if resp.status_code == 200:
            try:
                data = resp.json()
                if data.get("success"):
                    return True
            except:
                return True  # Si réponse 200 sans JSON

        logger.warning(f"Échec envoi ER OBR (HTTP {resp.status_code})")
        return False

    except Exception as e:
        logger.error(f"Erreur technique envoi mouvement ER : {e}")
        return False

# ─── ANNULATION FACTURE ────────────────────────────────────────────────────

@transaction.atomic
def annuler_facture_obr(facture, motif):
    if not motif.strip():
        raise ValueError("Motif d'annulation obligatoire")

    societe = facture.societe
    pending, _ = FacturePendingOBR.objects.get_or_create(facture=facture)

    payload = {
        "invoice_identifier": facture.invoice_identifier or "",
        "cn_motif": motif.strip()[:500]
    }

    url = f"{OBR_BASE_URL}{ENDPOINT_CANCEL_INVOICE}"
    headers = get_obr_headers(societe)

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT, verify=VERIFY_CERT)
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success"):
            raise ValueError(data.get("msg") or "Échec annulation OBR")

        # Succès → mise à jour facture
        facture.statut_obr = "ANNULE"
        facture.message_obr = data.get("msg", "Annulée")
        facture.save()

        # Restauration stock inverse (si c'était une FN) - Version compatible avec ton modèle
        if facture.type_facture == 'FN':
            for ligne in facture.lignes.filter(produit__isnull=False):
                produit = ligne.produit
                # On ne modifie pas quantite_stock (champ inexistant)
                # Le stock se recalcule automatiquement via le property stock_disponible
                pass

        pending.statut = "SUCCESS"
        pending.message = "Annulée avec succès"
        pending.save()

        logger.info(f"[OBR] Facture {facture.numero} annulée")
        return {'success': True, 'message': data.get("msg", "OK")}

    except Exception as e:
        logger.exception(f"[OBR] Échec annulation {facture.numero}")
        pending.statut = "FAILED"
        pending.message = str(e)
        pending.save()
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



def envoyer_mouvements_stock_en_attente(societe=None):
    """
    Envoie les mouvements de stock en attente vers l'OBR.
    Version anti-409 (conflit doublon) améliorée.
    """
    if societe:
        societes = [societe]
    else:
        from societe.models import Societe
        societes = Societe.objects.filter(obr_actif=True, obr_system_id__isnull=False)

    for soc in societes:
        try:
            headers = get_obr_headers(soc)
            url = f"{OBR_BASE_URL}{ENDPOINT_ADD_STOCK_MOVE}"

            sorties = SortieStock.objects.filter(
                societe=soc,
                statut_obr='EN_ATTENTE'
            ).select_related('entree_stock', 'entree_stock__produit')

            for sortie in sorties:
                try:
                    produit = sortie.entree_stock.produit if sortie.entree_stock else None
                    if not produit:
                        logger.warning(f"Sortie #{sortie.pk} : produit non trouvé")
                        continue

                    invoice_ref = ""
                    if hasattr(sortie, 'facture') and sortie.facture:
                        invoice_ref = sortie.facture.invoice_identifier or sortie.facture.numero_obr

                    # Création d'une date + identifiant unique pour éviter le 409
                    base_date = sortie.date_sortie.strftime("%Y-%m-%d %H:%M:%S")
                    unique_suffix = f"{sortie.pk}"   # On rend unique avec l'ID de la sortie

                    payload = {
                        "system_or_device_id": soc.obr_system_id.strip(),
                        "item_code": getattr(produit, 'code', f"PROD-{sortie.pk}"),
                        "item_designation": getattr(produit, 'designation', ''),
                        "item_quantity": float(sortie.quantite),
                        "item_measurement_unit": getattr(produit, 'unite', 'unité'),
                        "item_cost_price": float(getattr(sortie, 'prix', 0)),
                        "item_cost_price_currency": "BIF",
                        "item_movement_type": "SN",
                        "item_movement_invoice_ref": invoice_ref,
                        "item_movement_description": sortie.commentaire or f"Vente facture {getattr(sortie, 'date_sortie', '')}",
                        "item_movement_date": base_date   # On garde la date réelle
                    }

                    logger.info(f"[STOCK] Envoi sortie #{sortie.pk} | Produit: {produit.designation} | Qté: {sortie.quantite}")

                    resp = requests.post(url, json=payload, headers=headers, timeout=30, verify=VERIFY_CERT)

                    if resp.status_code == 200:
                        try:
                            data = resp.json()
                        except:
                            data = {}

                        success = data.get("success") is True
                        msg = str(data.get("msg", "")).lower().strip()

                        if success or "succès" in msg or "effectué avec succès" in msg or "operation" in msg:
                            SortieStock.objects.filter(pk=sortie.pk).update(
                                statut_obr="ENVOYE",
                                message_obr=data.get("msg", "Envoyé avec succès"),
                                date_envoi_obr=timezone.now(),
                            )
                            logger.info(f"[STOCK] Sortie #{sortie.pk} → ENVOYE avec succès")
                            continue

                    # Gestion spécifique du conflit 409
                    if resp.status_code == 409:
                        error_msg = "Conflit doublon (409) - mouvement déjà enregistré à l'OBR"
                    else:
                        try:
                            data = resp.json()
                            error_msg = data.get("msg", f"HTTP {resp.status_code}")
                        except:
                            error_msg = f"HTTP {resp.status_code}"

                    SortieStock.objects.filter(pk=sortie.pk).update(
                        statut_obr="ECHEC",
                        message_obr=error_msg
                    )
                    logger.warning(f"[STOCK] Échec sortie #{sortie.pk} : {error_msg} (Code {resp.status_code})")

                except Exception as inner_e:
                    logger.error(f"Erreur interne sortie stock #{sortie.pk}: {inner_e}")
                    SortieStock.objects.filter(pk=sortie.pk).update(
                        statut_obr="ECHEC",
                        message_obr=str(inner_e)[:200]
                    )

        except Exception as e:
            logger.error(f"Erreur globale envoi stock pour société {soc.nom}: {e}")
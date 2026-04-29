# obr_service.py — VERSION FINALE (alignée doc OBR v0.5)
# API totalement dynamique par société + vérification société active

import requests
import logging
import time
from decimal import Decimal

from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from django.db import transaction

from .models import Facture, FacturePendingOBR, LigneFacture
from stock.models import SortieStock, EntreeStock
from stock.obr_service import envoyer_entree_stock, envoyer_sortie_stock

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)
logging.getLogger("urllib3").setLevel(logging.ERROR)

# ─── CONFIGURATION ─────────────────────────────────────────────────────────
TIMEOUT = 45
MAX_RETRIES = 5
BASE_RETRY_DELAY = 8

CACHE_TOKEN_KEY_TEMPLATE = "obr_token_{societe_pk}"
CACHE_TOKEN_TIMEOUT = 2700  # 45 min

VERIFY_CERT = not settings.DEBUG
if not VERIFY_CERT:
    logger.warning("⚠️ VERIFY_CERT désactivé → uniquement pour développement !")

ENDPOINT_LOGIN          = "/login/"
ENDPOINT_ADD_INVOICE    = "/addInvoice_confirm/"
ENDPOINT_CANCEL_INVOICE = "/cancelInvoice/"
ENDPOINT_ADD_STOCK_MOVE = "/AddStockMovement/"


# ─── HELPERS DYNAMIQUES ─────────────────────────────────────────────────────
def get_obr_base_url(societe):
    """Retourne l'URL de base OBR pour une société."""
    url = getattr(societe, 'obr_base_url', None)
    if not url or not str(url).strip():
        raise ValueError(
            f"URL Base OBR non configurée pour la société '{societe.nom}' (pk={societe.pk}). "
            f"Veuillez renseigner le champ obr_base_url dans l'administration."
        )
    return str(url).strip().rstrip('/')


def build_obr_url(societe, endpoint):
    """Construit l'URL complète pour un endpoint donné."""
    return f"{get_obr_base_url(societe)}{endpoint}"


# ─── VÉRIFICATION SOCIÉTÉ ACTIVE ───────────────────────────────────────────
def check_societe_active(societe):
    """
    Vérifie que la société est active avant toute opération OBR.
    Lève une ValueError claire si la société est désactivée.
    """
    if not getattr(societe, 'actif', True):   # True par défaut si le champ n'existe pas encore
        logger.warning(f"[OBR] ACCÈS REFUSÉ - Société '{societe.nom}' (pk={societe.pk}) est désactivée.")
        raise ValueError(
            f"La société '{societe.nom}' est désactivée. "
            f"Impossible d'envoyer des données vers l'OBR."
        )


# ─── TOKEN ─────────────────────────────────────────────────────────────────
def get_obr_token(societe):
    cache_key = CACHE_TOKEN_KEY_TEMPLATE.format(societe_pk=societe.pk)
    token = cache.get(cache_key)
    if token:
        return token

    if not societe.obr_username or not societe.obr_password:
        raise ValueError(f"Identifiants OBR manquants pour la société '{societe.nom}' (pk={societe.pk})")

    # Vérification société active AVANT toute connexion
    check_societe_active(societe)

    url = build_obr_url(societe, ENDPOINT_LOGIN)

    payload = {
        "username": societe.obr_username,
        "password": societe.obr_password
    }

    logger.info(f"[OBR] Login société '{societe.nom}' → {url}")
    resp = requests.post(url, json=payload, timeout=TIMEOUT, verify=VERIFY_CERT)
    resp.raise_for_status()
    data = resp.json()

    if not data.get("success"):
        raise ValueError(f"Login OBR échoué pour '{societe.nom}' : {data.get('msg')}")

    token = data["result"]["token"]
    cache.set(cache_key, token, CACHE_TOKEN_TIMEOUT)
    logger.info(f"[OBR] Token obtenu et mis en cache pour société '{societe.nom}'")
    return token


def invalidate_obr_token(societe):
    """Invalide le token en cache pour une société donnée."""
    cache_key = CACHE_TOKEN_KEY_TEMPLATE.format(societe_pk=societe.pk)
    cache.delete(cache_key)
    logger.info(f"[OBR] Token invalidé pour société '{societe.nom}'")


def get_obr_headers(societe):
    """Retourne les headers avec token Bearer."""
    return {
        "Authorization": f"Bearer {get_obr_token(societe)}",
        "Content-Type": "application/json"
    }


# ─── PAYLOAD FACTURE (inchangé) ────────────────────────────────────────────
def build_invoice_payload(facture):
    societe = facture.societe
    client  = facture.client
    lignes  = facture.lignes.select_related('produit', 'service').all()

    datetime_str = f"{facture.date_facture.strftime('%Y-%m-%d')} {facture.heure_facture.strftime('%H:%M:%S')}"

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

    if facture.type_facture in ['FA', 'RC'] and facture.facture_originale:
        payload["invoice_ref"] = facture.facture_originale.numero[:30]
        payload["cn_motif"] = facture.motif_avoir[:500] if facture.motif_avoir else "Avoir / Annulation"

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


# ─── ENVOI FACTURE ─────────────────────────────────────────────────────────
def envoyer_facture_obr(facture):
    """Envoie la facture à l'OBR uniquement si la société est active."""
    societe = facture.societe
    pending, _ = FacturePendingOBR.objects.get_or_create(facture=facture)
    pending.retry_count = (pending.retry_count or 0) + 1
    pending.save(update_fields=['retry_count'])

    try:
        # VÉRIFICATION SOCIÉTÉ ACTIVE
        check_societe_active(societe)

        payload = build_invoice_payload(facture)
        url = build_obr_url(societe, ENDPOINT_ADD_INVOICE)

        logger.info(f"[OBR] Début envoi facture {facture.numero} | Société: {societe.nom} → {url}")

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
                    logger.warning(f"[OBR] Token invalide pour '{societe.nom}' → refresh")
                    invalidate_obr_token(societe)
                    continue

                if resp.status_code == 200:
                    data = resp.json()

                    if data.get("success"):
                        facture.statut_obr = "ENVOYE"
                        facture.message_obr = data.get("msg", "Succès")
                        facture.date_envoi_obr = timezone.now()
                        facture.obr_registered_number = data.get("result", {}).get("invoice_registered_number", "")
                        facture.electronic_signature = data.get("electronic_signature", "")
                        facture.save()

                        pending.statut = "SUCCESS"
                        pending.message = data.get("msg", "OK")
                        pending.save()

                        # Synchro Stock
                        try:
                            if facture.type_facture == 'FN':
                                sorties = SortieStock.objects.filter(
                                    facture=facture, statut_obr='EN_ATTENTE'
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
                                traiter_stock_pour_avoir(facture)

                        except Exception as stock_err:
                            logger.warning(f"Facture envoyée mais erreur synchro stock: {stock_err}", exc_info=True)

                        return {'success': True, 'message': data.get("msg", "Facture envoyée avec succès")}

                data = resp.json() if resp.headers.get('content-type', '').startswith('application/json') else {}
                msg = data.get("msg") or f"Erreur HTTP {resp.status_code}"
                logger.warning(f"[OBR] Échec tentative {attempt} pour '{societe.nom}': {msg}")
                pending.message = msg
                pending.save(update_fields=['message'])

            except requests.RequestException as e:
                msg = f"Tentative {attempt} - Erreur réseau: {str(e)}"
                logger.error(f"[OBR] {msg} | Société: {societe.nom}")
                pending.message = msg
                pending.save(update_fields=['message'])
                time.sleep(BASE_RETRY_DELAY)

        pending.statut = "FAILED"
        pending.save()
        return {'success': False, 'message': f"Échec après {MAX_RETRIES} tentatives"}

    except ValueError as ve:
        logger.warning(f"[OBR] Validation échouée pour facture {facture.numero}: {ve}")
        pending.statut = "FAILED"
        pending.message = str(ve)
        pending.save()
        return {'success': False, 'message': str(ve)}

    except Exception as e:
        logger.exception(f"[OBR] Erreur critique facture {facture.numero} | Société: {societe.nom}")
        pending.statut = "FAILED"
        pending.message = str(e)
        pending.save()
        return {'success': False, 'message': str(e)}


# ─── ANNULATION FACTURE ────────────────────────────────────────────────────
def annuler_facture_obr(facture, motif: str):
    if not motif or not motif.strip():
        return {'success': False, 'message': "Motif obligatoire"}

    motif = motif.strip()[:500]
    societe = facture.societe

    try:
        # Vérification société active
        check_societe_active(societe)

        if facture.statut_obr == 'ENVOYE':
            if not facture.invoice_identifier:
                return {'success': False, 'message': "invoice_identifier manquant"}

            url = build_obr_url(societe, ENDPOINT_CANCEL_INVOICE)

            payload = {
                "invoice_identifier": facture.invoice_identifier,
                "cn_motif": motif
            }

            logger.info(f"[OBR] Annulation facture {facture.numero} | Société: {societe.nom}")

            resp = requests.post(
                url, json=payload, headers=get_obr_headers(societe),
                timeout=TIMEOUT, verify=VERIFY_CERT
            )

            if resp.status_code in (401, 403):
                invalidate_obr_token(societe)
                resp = requests.post(
                    url, json=payload, headers=get_obr_headers(societe),
                    timeout=TIMEOUT, verify=VERIFY_CERT
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

        with transaction.atomic():
            pending, _ = FacturePendingOBR.objects.get_or_create(facture=facture)

            facture.statut_obr = 'ANNULE'
            facture.message_obr = message_obr
            facture.motif_avoir = f"Annulation : {motif}"
            facture.date_annulation = timezone.now()

            facture.save(update_fields=['statut_obr', 'message_obr', 'motif_avoir', 'date_annulation'])
            pending.statut = "SUCCESS"
            pending.message = message_obr
            pending.save(update_fields=['statut', 'message'])

        return {'success': True, 'message': message_obr}

    except Exception as e:
        logger.exception(f"[OBR Cancel] Erreur facture {facture.numero} | Société: {societe.nom}")
        try:
            pending, _ = FacturePendingOBR.objects.get_or_create(facture=facture)
            pending.statut = "FAILED"
            pending.message = str(e)[:500]
            pending.save(update_fields=['statut', 'message'])
        except:
            pass
        return {'success': False, 'message': str(e)}


# ─── NETTOYAGE DES DOUBLONS (inchangé) ─────────────────────────────────────
def nettoyer_doublons_stock():
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
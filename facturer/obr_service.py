import requests
import logging
import time
from decimal import Decimal

from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from django.db import transaction

from .models import Facture, FacturePendingOBR
from stock.models import SortieStock, EntreeStock
from stock.obr_service import envoyer_entree_stock, envoyer_sortie_stock

logger = logging.getLogger(__name__)

# ─── CONFIGURATION ─────────────────────────────────────────────────────────
TIMEOUT = 45
MAX_RETRIES = 5
BASE_RETRY_DELAY = 8

CACHE_TOKEN_KEY_TEMPLATE = "obr_token_{societe_pk}"
CACHE_TOKEN_TIMEOUT = 2700  # 45 minutes

VERIFY_CERT = not settings.DEBUG
if not VERIFY_CERT:
    logger.warning("⚠️ VERIFY_CERT désactivé → Mode développement uniquement !")

ENDPOINT_LOGIN          = "/login/"
ENDPOINT_ADD_INVOICE    = "/addInvoice_confirm/"
ENDPOINT_CANCEL_INVOICE = "/cancelInvoice/"


# ─── URL DYNAMIQUE (Test / Production) ─────────────────────────────────────
def get_obr_base_url(societe):
    """9443 = Test, 8443 = Production"""
    host = "ebms.obr.gov.bi"
    port = 9443 if getattr(societe, 'obr_api_test', True) else 8443
    return f"https://{host}:{port}/ebms_api"


def get_obr_headers(societe):
    return {
        "Authorization": f"Bearer {get_obr_token(societe)}",
        "Content-Type": "application/json"
    }


# ─── TOKEN ─────────────────────────────────────────────────────────────────
def get_obr_token(societe):
    cache_key = CACHE_TOKEN_KEY_TEMPLATE.format(societe_pk=societe.pk)
    token = cache.get(cache_key)
    if token:
        return token

    base_url = get_obr_base_url(societe)
    url = f"{base_url}{ENDPOINT_LOGIN}"

    payload = {
        "username": societe.obr_username,
        "password": societe.obr_password
    }

    resp = requests.post(url, json=payload, timeout=TIMEOUT, verify=VERIFY_CERT)
    resp.raise_for_status()
    data = resp.json()

    if not data.get("success"):
        raise ValueError(f"Login OBR échoué : {data.get('msg')}")

    token = data["result"]["token"]
    cache.set(cache_key, token, CACHE_TOKEN_TIMEOUT)
    logger.info(f"[OBR] Token obtenu pour {societe.nom}")
    return token


def invalidate_obr_token(societe):
    cache_key = CACHE_TOKEN_KEY_TEMPLATE.format(societe_pk=societe.pk)
    cache.delete(cache_key)


# ─── PAYLOAD FACTURE ───────────────────────────────────────────────────────
def build_invoice_payload(facture):
    """Construction du payload OBR"""
    
    # === CORRECTION IMPORTANTE ===
    # On ne régénère l'identifiant QUE s'il n'existe pas encore
    if not facture.invoice_identifier:
        facture.generate_invoice_identifier()
        facture.save(update_fields=['invoice_identifier'])
    
    print(f"[DEBUG] invoice_identifier envoyé → {facture.invoice_identifier}")

    # ... reste de ton code ...

    societe = facture.societe
    client = facture.client
    lignes = facture.lignes.select_related('produit', 'service', 'taux_tva').all()

        # Synchronisation stricte avec l'identifiant
    try:
        date_part = facture.invoice_identifier.split('/')[2]  # YYYYMMDDHHMMSS
        y, m, d = date_part[0:4], date_part[4:6], date_part[6:8]
        h, min_, s = date_part[8:10], date_part[10:12], date_part[12:14]
        invoice_date_str = f"{y}-{m}-{d} {h}:{min_}:{s}"
    except:
        invoice_date_str = timezone.now().strftime("%Y-%m-%d %H:%M:%S")

    payment_mapping = {'CAISSE': '1', 'BANQUE': '2', 'CREDIT': '3', 'AUTRES': '4'}
    payment_type_obr = payment_mapping.get(facture.mode_paiement, '1')

    payload = {
        "invoice_number": str(facture.numero_obr)[:30],
        "invoice_date": invoice_date_str,
        "invoice_type": str(facture.type_facture)[:2],
        "tp_type": "2",
        "tp_name": str(societe.nom)[:100],
        "tp_TIN": str(societe.nif)[:30],
        "tp_trade_number": str(getattr(societe, 'registre', ''))[:20],
        "tp_postal_number": str(getattr(societe, 'boite_postal', ''))[:20],
        "tp_phone_number": str(getattr(societe, 'telephone', ''))[:20],
        "tp_address_province": str(getattr(societe, 'province', ''))[:50],
        "tp_address_commune": str(getattr(societe, 'commune', ''))[:50],
        "tp_address_quartier": str(getattr(societe, 'quartier', ''))[:50],
        "tp_address_avenue": str(getattr(societe, 'avenue', ''))[:50],
        "tp_address_rue": "",
        "tp_address_number": str(getattr(societe, 'numero', ''))[:10],
        "vat_taxpayer": "1" if getattr(societe, 'assujeti_tva', False) else "0",
        "ct_taxpayer": "1" if getattr(societe, 'assujeti_tc', False) else "0",
        "tl_taxpayer": "1" if getattr(societe, 'assujeti_pfl', False) else "0",
        "tp_fiscal_center": getattr(societe, 'centre_fiscal', 'DGC'),
        "tp_activity_sector": str(getattr(societe, 'secteur', 'SERVICE MARCHAND'))[:250],
        "tp_legal_form": str(getattr(societe, 'forme', 'SARL'))[:50],
        "payment_type": payment_type_obr,
        "invoice_currency": str(facture.devise)[:5],
        "customer_name": client.nom,
        "customer_TIN": getattr(client, 'nif', ''),
        "customer_address": str(getattr(client, 'adresse_complete', ''))[:100],
        "vat_customer_payer": "1" if getattr(client, 'assujetti_tva', False) else "0",
        "cancelled_invoice_ref": "",
        "invoice_ref": "",
        "cn_motif": "",
        "invoice_identifier": facture.invoice_identifier,
        "invoice_items": []
    }

    # ... (le reste pour les lignes et avoirs reste le même)

    # Gestion des avoirs
    if facture.type_facture in ['FA', 'RC'] and facture.facture_originale:
        payload["invoice_ref"] = facture.facture_originale.numero[:30]
        payload["cn_motif"] = (facture.motif_avoir or "Avoir / Note de crédit")[:500]

    # Lignes de la facture
    for ligne in lignes:
        prix_ht = float(getattr(ligne, 'prix_unitaire_ht', 0) or 0)
        quantite = float(ligne.quantite or 0)
        taux = float(getattr(ligne.taux_tva, 'valeur', 0) or 0)

        montant_ht = round(prix_ht * quantite, 2)
        montant_tva = round(montant_ht * taux / 100, 2)
        montant_ttc = round(montant_ht + montant_tva, 2)

        payload["invoice_items"].append({
            "item_designation": str(ligne.designation)[:500],
            "item_quantity": str(quantite),
            "item_price": str(prix_ht),
            "item_ct": "0",
            "item_tl": "0",
            "item_ott_tax": "0",
            "item_tsce_tax": "0",
            "item_price_nvat": str(montant_ht),
            "vat": str(montant_tva),
            "item_price_wvat": str(montant_ttc),
            "item_total_amount": str(montant_ttc),
        })

    return payload


# ─── ENVOI FACTURE ─────────────────────────────────────────────────────────
def envoyer_facture_obr(facture):
    societe = facture.societe
    pending, _ = FacturePendingOBR.objects.get_or_create(facture=facture)
    pending.retry_count = (pending.retry_count or 0) + 1
    pending.save(update_fields=['retry_count'])

    try:
        payload = build_invoice_payload(facture)
        base_url = get_obr_base_url(societe)
        url = f"{base_url}{ENDPOINT_ADD_INVOICE}"

        logger.info(f"[OBR] Envoi facture {facture.numero} → {url}")

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
                                ).select_related('entree_stock')
                                for sortie in sorties:
                                    result = envoyer_sortie_stock(sortie)
                                    # ... votre logique de mise à jour sortie ...

                            elif facture.type_facture == 'FA':
                                traiter_stock_pour_avoir(facture)
                        except Exception as stock_err:
                            logger.warning(f"Erreur synchro stock: {stock_err}")

                        return {'success': True, 'message': data.get("msg", "Facture envoyée")}

                # Erreur OBR
                try:
                    error_data = resp.json()
                    msg = error_data.get("msg", f"HTTP {resp.status_code}")
                except:
                    msg = resp.text[:300]

                logger.warning(f"[OBR] Échec tentative {attempt}: {msg}")
                pending.message = msg
                pending.save(update_fields=['message'])

            except requests.RequestException as e:
                msg = f"Erreur réseau: {e}"
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
        pending.message = str(e)[:500]
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


@transaction.atomic
def traiter_stock_pour_avoir(facture):
    """Met à jour et envoie les entrées ER pour les factures d'avoir (FA)"""
    if facture.type_facture != 'FA':
        return

    logger.info(f"[STOCK] Traitement avoir FA {facture.numero}")

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
                entree.message_obr = msg or 'Envoyé avec succès'
                entree.save(update_fields=['statut_obr', 'message_obr'])
            else:
                entree.statut_obr = 'ECHEC'
                entree.message_obr = msg or 'Échec envoi'
                entree.save(update_fields=['statut_obr', 'message_obr'])

        except Exception as e:
            logger.error(f"[STOCK] Erreur sur entrée ER {entree.pk}: {e}", exc_info=True)
            entree.statut_obr = 'ECHEC'
            entree.message_obr = str(e)[:500]
            entree.save(update_fields=['statut_obr', 'message_obr'])


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
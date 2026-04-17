import warnings
from urllib3.exceptions import InsecureRequestWarning

warnings.simplefilter('ignore', InsecureRequestWarning)
# obr_service.py
import requests
import logging
import time
from decimal import Decimal
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_http_methods
from .models import Facture, FacturePendingOBR
import json   # ← AJOUTE ÇA ICI

logger = logging.getLogger(__name__)

# ───────── CONFIGURATION ─────────
OBR_BASE_URL = "https://ebms.obr.gov.bi:9443/ebms_api"
TIMEOUT = 45
MAX_RETRIES = 5
BASE_RETRY_DELAY = 8

CACHE_TOKEN_KEY_TEMPLATE = "obr_token_{societe_pk}"
CACHE_TOKEN_TIMEOUT = 2700  # 45 min

VERIFY_CERT = not settings.DEBUG
# Après OBR_BASE_URL
ENDPOINT_LOGIN         = "/login/"
ENDPOINT_ADD_INVOICE   = "/addInvoice_confirm/"
ENDPOINT_CANCEL_INVOICE = "/cancelInvoice/"


def _login(societe):
    """
    Authentification OBR et récupération du token.
    """
    if not all([societe.obr_username, societe.obr_password]):
        raise Exception("Identifiants OBR non configurés pour cette société.")

    url = OBR_BASE_URL + ENDPOINT_LOGIN
    payload = {
        "username": societe.obr_username,
        "password": societe.obr_password
    }

    try:
        resp = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=TIMEOUT,
            verify=False
        )
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success"):
            raise Exception(data.get("msg") or "Échec authentification OBR")

        token = data.get("result", {}).get("token")
        if not token:
            raise Exception("Aucun token retourné par OBR")

        logger.info(f"[OBR] Token obtenu pour {societe.nom}")
        return token

    except requests.RequestException as e:
        raise Exception(f"Erreur réseau login OBR : {str(e)}")
    except Exception as e:
        raise Exception(f"Erreur login OBR : {str(e)}")



# ───────── HELPERS ─────────

def _get_token(societe):
    cache_key = CACHE_TOKEN_KEY_TEMPLATE.format(societe_pk=societe.pk)
    token = cache.get(cache_key)

    if token:
        logger.debug(f"[OBR] Token from cache for {societe.pk}")
        return token

    if not societe.obr_username or not societe.obr_password:
        raise ValueError("Identifiants OBR manquants pour cette société.")

    url = f"{OBR_BASE_URL}/login/"
    payload = {
        "username": societe.obr_username,
        "password": societe.obr_password
    }

    try:
        resp = requests.post(url, json=payload, timeout=TIMEOUT, verify=VERIFY_CERT)
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success"):
            raise ValueError(f"Login OBR failed: {data.get('msg')}")

        token = data["result"].get("token")
        if not token:
            raise ValueError("No token in login response")

        cache.set(cache_key, token, CACHE_TOKEN_TIMEOUT)
        logger.info(f"[OBR] Token refreshed for {societe.pk}")
        return token

    except requests.RequestException as e:
        logger.error(f"[OBR] Erreur login: {e}")
        raise


def _get_headers(societe):
    return {
        "Authorization": f"Bearer {_get_token(societe)}",
        "Content-Type": "application/json"
    }


def _build_invoice_payload(facture):
    """
    Construit le payload complet pour OBR pour FN, FA, RC.
    """
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

    # Pour FA ou RC → référence facture originale et motif
    if facture.type_facture in ['FA', 'RC'] and facture.facture_originale:
        payload["invoice_ref"] = str(facture.facture_originale.numero)[:30]
        payload["cn_motif"] = str(getattr(facture, 'motif_avoir', 'Avoir / Annulation'))[:500]

    # Lignes
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

# ───────── ENVOI FACTURE ─────────
def envoyer_facture_obr(facture):
    societe = facture.societe
    pending, _ = FacturePendingOBR.objects.get_or_create(facture=facture)
    pending.retry_count = (pending.retry_count or 0) + 1
    pending.save(update_fields=['retry_count'])

    try:
        token = _login(societe)

        # Ancienne ligne à supprimer/commenter :
        # payload = _build_invoice_payload(facture)

        # Nouvelle ligne correcte :
        payload = _build_invoice_payload(facture)
        print("\n" + "="*50)
        print(f"PAYLOAD ENVOYÉ À OBR (Facture {facture.numero})")
        print("="*50)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        print("="*50 + "\n")

        # LOG DEBUG CRITIQUE
        logger.info(f"[DEBUG] Payload facture {facture.numero}")
        logger.info(json.dumps(payload, indent=2, ensure_ascii=False))

        url = OBR_BASE_URL + ENDPOINT_ADD_INVOICE

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = requests.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
                    timeout=TIMEOUT,
                    verify=False
                )

                logger.info(f"[OBR] Tentative {attempt} → HTTP {resp.status_code}")

                if resp.status_code in (401, 403):
                    logger.warning("Token invalide → refresh")
                    token = _login(societe)
                    if attempt < MAX_RETRIES:
                        time.sleep(BASE_RETRY_DELAY)
                        continue

                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("success"):
                        facture.signature_obr = data.get("electronic_signature", "")
                        facture.statut_obr = "ENVOYE"
                        facture.message_obr = data.get("msg", "Succès")
                        facture.date_envoi_obr = timezone.now()
                        facture.save()

                        pending.statut = "SUCCESS"
                        pending.message = data.get("msg", "OK")
                        pending.save()

                        return {'success': True, 'message': data.get("msg", "Envoyée avec succès")}

                # Erreur 400 ou autre
                try:
                    data = resp.json()
                    msg = data.get("msg") or f"Erreur {resp.status_code}"
                except:
                    msg = f"Erreur {resp.status_code} - réponse non JSON"

                logger.warning(f"[OBR] Échec tentative {attempt}: {msg}")
                pending.message = msg
                pending.save(update_fields=['message'])

            except requests.RequestException as e:
                msg = f"Tentative {attempt} réseau: {str(e)}"
                logger.error(msg)
                pending.message = msg
                pending.save(update_fields=['message'])
                time.sleep(BASE_RETRY_DELAY)

        pending.statut = "FAILED"
        pending.save()
        return {'success': False, 'message': f"Échec après {MAX_RETRIES} tentatives"}

    except Exception as e:
        logger.exception(f"[OBR] Critique {facture.numero}")
        pending.statut = "FAILED"
        pending.message = str(e)
        pending.save()
        return {'success': False, 'message': str(e)}
"""
@login_required
@require_POST
def ajax_envoyer_obr(request, pk):
    societe, err = _check_droit(request)
    if err:
        return JsonResponse({'ok': False, 'error': err}, status=403)

    facture = get_object_or_404(Facture, pk=pk, societe=societe)

    if facture.statut_obr != 'EN_ATTENTE':
        return JsonResponse({
            'ok': False,
            'error': f"Impossible d'envoyer : statut actuel est {facture.get_statut_obr_display()}"
        }, status=400)

    if facture.lignes.count() == 0:
        return JsonResponse({'ok': False, 'error': 'La facture est vide'}, status=400)

    try:
        with transaction.atomic():
            result = envoyer_facture_obr(facture)

            # Protection contre retour invalide
            if result is None:
                logger.error(f"envoyer_facture_obr a renvoyé None pour facture {facture.pk}")
                raise ValueError("Erreur interne : aucune réponse de l'OBR")

            if not isinstance(result, dict):
                logger.error(f"envoyer_facture_obr a renvoyé {type(result)} au lieu de dict")
                raise ValueError("Erreur interne : réponse OBR invalide")

            if not result.get('success'):
                # On prend le message le plus précis possible
                error_msg = result.get('message') or result.get('msg') or 'Échec envoi OBR (raison inconnue)'
                raise ValueError(error_msg)

            # Mise à jour facture
            facture.statut_obr = 'ENVOYE'
            facture.message_obr = result.get('message') or result.get('msg') or 'Envoyée avec succès'
            facture.date_envoi_obr = timezone.now()

            # Champs utiles à conserver
            if 'electronic_signature' in result:
                facture.signature_obr = result['electronic_signature']
            if 'result' in result and isinstance(result['result'], dict):
                facture.obr_registered_number = result['result'].get('invoice_registered_number', '')
                facture.obr_registered_date = result['result'].get('invoice_registered_date')

            facture.save(update_fields=[
                'statut_obr', 'message_obr', 'date_envoi_obr',
                'signature_obr', 'obr_registered_number', 'obr_registered_date'
            ])

            # Gestion stock (à compléter avec ton code existant)
            # Exemple minimal :
            # for ligne in facture.lignes.filter(produit__isnull=False):
            #     produit = ligne.produit
            #     produit.quantite_stock = (produit.quantite_stock or 0) - ligne.quantite
            #     produit.save(update_fields=['quantite_stock'])

            return JsonResponse({
                'ok': True,
                'message': 'Facture envoyée avec succès à l\'OBR',
                'numero_obr': facture.obr_registered_number,
                'signature': facture.signature_obr,
                'date_envoi': facture.date_envoi_obr.isoformat() if facture.date_envoi_obr else None,
            })

    except ValueError as ve:
        # Erreurs métier → 400
        return JsonResponse({
            'ok': False,
            'error': str(ve) or 'Erreur lors de l\'envoi à l\'OBR'
        }, status=400)

    except Exception as e:
        traceback.print_exc()
        logger.error(f"Erreur critique envoi OBR facture {pk}: {str(e)}")
        return JsonResponse({
            'ok': False,
            'error': 'Une erreur serveur est survenue. Veuillez contacter le support.'
        }, status=500)
"""
@login_required
@require_POST
def ajax_envoyer_obr(request, pk):
    societe, err = _check_droit(request)
    if err:
        return JsonResponse({'ok': False, 'error': err}, status=403)

    facture = get_object_or_404(Facture, pk=pk, societe=societe)

    if facture.statut_obr != 'EN_ATTENTE':
        return JsonResponse({
            'ok': False,
            'error': f"Impossible d'envoyer : statut actuel est {facture.get_statut_obr_display()}"
        }, status=400)

    if facture.lignes.count() == 0:
        return JsonResponse({'ok': False, 'error': 'La facture est vide'}, status=400)

    try:
        with transaction.atomic():
            # Envoi de la facture à l'OBR
            result = envoyer_facture_obr(facture)

            # Protection contre retour invalide
            if not result or not isinstance(result, dict):
                raise ValueError("Erreur interne : réponse OBR invalide")

            if not result.get('success'):
                error_msg = result.get('message') or result.get('msg') or 'Échec envoi OBR'
                raise ValueError(error_msg)

            # Mise à jour statut facture
            facture.statut_obr = 'ENVOYE'
            facture.message_obr = result.get('message') or result.get('msg') or 'Envoyée avec succès'
            facture.date_envoi_obr = timezone.now()

            if 'electronic_signature' in result:
                facture.signature_obr = result['electronic_signature']
            if 'result' in result and isinstance(result['result'], dict):
                facture.obr_registered_number = result['result'].get('invoice_registered_number', '')
                facture.obr_registered_date = result['result'].get('invoice_registered_date')

            facture.save(update_fields=[
                'statut_obr', 'message_obr', 'date_envoi_obr',
                'signature_obr', 'obr_registered_number', 'obr_registered_date'
            ])

            # ───── Gestion stock FN / FA / RC ─────
            for ligne in facture.lignes.filter(produit__isnull=False):
                produit = ligne.produit
                qte = ligne.quantite or 0

                if facture.type_facture == 'FN':
                    produit.quantite_stock = (produit.quantite_stock or 0) - qte
                    mouvement_type = "SN"  # Sortie normale
                    mouvement_qte = qte
                elif facture.type_facture in ['FA', 'RC']:
                    produit.quantite_stock = (produit.quantite_stock or 0) + qte
                    mouvement_type = "RA"  # Retour / Avoir
                    mouvement_qte = -qte  # signe négatif pour OBR si nécessaire
                else:
                    continue

                produit.save(update_fields=['quantite_stock'])

                # Envoi mouvement stock à l’OBR
                success, msg = envoyer_mouvement_stock_obr(
                    produit=produit,
                    quantite=mouvement_qte,
                    type_mouvement=mouvement_type,
                    facture_ref=str(facture.numero),
                    description=f"Facture {facture.numero}"
                )

                if not success:
                    logger.warning(f"[OBR] Échec mouvement stock produit {produit.pk}: {msg}")

            return JsonResponse({
                'ok': True,
                'message': f'Facture envoyée avec succès à l\'OBR',
                'numero_obr': facture.obr_registered_number,
                'signature': facture.signature_obr,
                'date_envoi': facture.date_envoi_obr.isoformat() if facture.date_envoi_obr else None,
            })

    except ValueError as ve:
        return JsonResponse({'ok': False, 'error': str(ve)}, status=400)
    except Exception as e:
        logger.exception(f"Erreur critique envoi OBR facture {pk}: {str(e)}")
        return JsonResponse({
            'ok': False,
            'error': 'Une erreur serveur est survenue. Veuillez contacter le support.'
        }, status=500)
"""
def annuler_facture_obr(facture, motif):
    if not motif.strip():
        raise ValueError("Motif d'annulation obligatoire")

    societe = facture.societe
    pending, _ = FacturePendingOBR.objects.get_or_create(facture=facture)

    payload = {
        "invoice_identifier": str(facture.invoice_identifier or ""),
        "cn_motif": str(motif.strip())[:500]
    }

    url = f"{OBR_BASE_URL}/cancelInvoice/"

    try:
        headers = _get_headers(societe)
        resp = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT, verify=VERIFY_CERT)
        resp.raise_for_status()
        data = resp.json()

        if data.get("success"):
            facture.statut_obr = "ANNULE"
            facture.message_obr = data.get("msg", "")
            facture.save(update_fields=['statut_obr', 'message_obr'])

            pending.statut = "SUCCESS"
            pending.message = data.get("msg", "")
            pending.save()

            logger.info(f"[OBR] Annulation OK {facture.numero}")
            return {'success': True, 'message': data.get("msg", "OK")}

        else:
            msg = data.get("msg", "Échec")
            pending.message = msg
            pending.save()
            return {'success': False, 'message': msg}

    except requests.RequestException as e:
        logger.error(f"[OBR] Réseau annulation {facture.numero}: {e}")
        pending.message = str(e)
        pending.save()
        return {'success': False, 'message': f"Réseau: {str(e)}"}
    except Exception as e:
        logger.exception(f"[OBR] Critique annulation {facture.numero}")
        pending.message = str(e)
        pending.save()
        return {'success': False, 'message': str(e)}
"""
def annuler_facture_obr(facture, motif):
    if not motif.strip():
        raise ValueError("Motif d'annulation obligatoire")

    societe = facture.societe
    pending, _ = FacturePendingOBR.objects.get_or_create(facture=facture)

    payload = {
        "invoice_identifier": str(facture.invoice_identifier or ""),
        "cn_motif": str(motif.strip())[:500]
    }

    url = f"{OBR_BASE_URL}/cancelInvoice/"

    try:
        headers = _get_headers(societe)
        resp = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT, verify=VERIFY_CERT)
        resp.raise_for_status()
        data = resp.json()

        if data.get("success"):
            facture.statut_obr = "ANNULE"
            facture.message_obr = data.get("msg", "")
            facture.save(update_fields=['statut_obr', 'message_obr'])

            pending.statut = "SUCCESS"
            pending.message = data.get("msg", "")
            pending.save()

            # Restauration stock + suppression mouvements
            if facture.type_facture in ['FN', 'FA', 'RC']:
                # On cherche par facture.numero (plus fiable que juste "Facture")
                mouvements = SortieStock.objects.filter(
                    commentaire__icontains=f"Facture {facture.numero}"
                )
                for mouv in mouvements:
                    # Inverser le mouvement
                    if mouv.type_sortie == "SN":  # vente → on ajoute au stock
                        delta = +mouv.quantite
                    elif mouv.type_sortie == "RA":  # avoir → on soustrait
                        delta = -mouv.quantite
                    else:
                        delta = 0

                    if delta != 0:
                        produit = mouv.produit  # suppose que tu as ajouté produit = entree_stock.produit
                        produit.quantite_stock = (produit.quantite_stock or Decimal('0')) + delta
                        produit.save(update_fields=['quantite_stock'])

                # Suppression
                mouvements.delete()

            logger.info(f"[OBR] Annulation OK + stock restauré {facture.numero}")
            return {'success': True, 'message': data.get("msg", "OK")}

        else:
            msg = data.get("msg", "Échec")
            pending.message = msg
            pending.save(update_fields=['message'])
            return {'success': False, 'message': msg}

    except requests.RequestException as e:
        logger.error(f"[OBR] Réseau annulation {facture.numero}: {e}")
        pending.message = str(e)
        pending.save(update_fields=['message'])
        return {'success': False, 'message': f"Réseau: {str(e)}"}
    except Exception as e:
        logger.exception(f"[OBR] Critique annulation {facture.numero}")
        pending.message = str(e)
        pending.save(update_fields=['message'])
        return {'success': False, 'message': str(e)}
# ───────── MOUVEMENT STOCK ─────────
"""
def envoyer_mouvement_stock_obr(produit, quantite, type_mouvement, facture_ref="", description=""):
    societe = produit.societe

    payload = {
        "system_or_device_id": getattr(societe, 'obr_system_id', f"ws{societe.pk}")[:100],
        "item_code": str(getattr(produit, 'code', produit.pk))[:30],
        "item_designation": str(produit.designation or "")[:500],
        "item_quantity": float(quantite),
        "item_measurement_unit": str(getattr(produit, 'unite_mesure', 'pcs') or "pcs")[:20],
        "item_cost_price": float(getattr(produit, 'prix_achat', 0) or 0),
        "item_cost_price_currency": "BIF",
        "item_movement_type": str(type_mouvement or "SN")[:5],
        "item_movement_invoice_ref": str(facture_ref or "")[:30],
        "item_movement_description": str(description or "")[:500],
        "item_movement_date": timezone.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    url = f"{OBR_BASE_URL}/AddStockMovement/"

    try:
        headers = _get_headers(societe)
        resp = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT, verify=VERIFY_CERT)
        resp.raise_for_status()
        data = resp.json()

        if data.get("success"):
            logger.info(f"[OBR] Mouvement {type_mouvement} OK")
            return True
        else:
            logger.warning(f"[OBR] Échec mouvement: {data.get('msg')}")
            return False

    except Exception as e:
        logger.error(f"[OBR] Erreur mouvement stock: {e}")
        return False
    """
def envoyer_mouvement_stock_obr(
    produit,
    quantite: Decimal,
    type_mouvement: str,
    facture_ref: str = "",
    description: str = ""
) -> tuple[bool, str | None]:
    """
    Envoie un mouvement de stock à l'OBR avec retries et meilleure gestion d'erreurs.
    
    Args:
        produit: Instance Produit
        quantite: Quantité (positive ou négative selon mouvement)
        type_mouvement: Code OBR (ex: 'SN', 'RA', 'SAJ'...)
        facture_ref: Numéro de facture (optionnel)
        description: Description humaine (optionnel)
    
    Returns:
        tuple (success: bool, message_erreur: str | None)
    """
    societe = produit.societe

    # Validation minimale en amont
    if not societe:
        return False, "Société non associée au produit"

    if not isinstance(quantite, (int, float, Decimal)) or quantite == 0:
        return False, "Quantité invalide ou nulle"

    # Préparation payload avec valeurs sécurisées et tronquées
    payload = {
        "system_or_device_id": str(getattr(societe, 'obr_system_id', f"ws{societe.pk}"))[:100],
        "item_code": str(getattr(produit, 'code', produit.pk))[:30],
        "item_designation": str(produit.designation or "Produit sans désignation")[:500],
        "item_quantity": float(quantite),  # OBR attend float
        "item_measurement_unit": str(getattr(produit, 'unite', 'pcs') or 'pcs')[:20],
        "item_cost_price": float(getattr(produit, 'prix_achat', 0) or 0),
        "item_cost_price_currency": "BIF",
        "item_movement_type": str(type_mouvement or "SN")[:5],
        "item_movement_invoice_ref": str(facture_ref or "")[:30],
        "item_movement_description": str(description or "Mouvement automatique")[:500],
        "item_movement_date": timezone.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    url = f"{OBR_BASE_URL}/AddStockMovement/"

    headers = _get_headers(societe)

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=TIMEOUT,
                verify=VERIFY_CERT
            )

            # Gestion token expiré
            if resp.status_code in (401, 403):
                cache.delete(CACHE_TOKEN_KEY_TEMPLATE.format(societe_pk=societe.pk))
                headers = _get_headers(societe)
                if attempt < MAX_RETRIES:
                    time.sleep(BASE_RETRY_DELAY * attempt)
                    continue
                else:
                    last_error = "Token invalide après plusieurs tentatives"
                    break

            resp.raise_for_status()
            data = resp.json()

            if data.get("success") is True:
                logger.info(
                    f"[OBR] Mouvement {type_mouvement} OK | "
                    f"facture={facture_ref} | produit={produit.designation} | "
                    f"qte={quantite}"
                )
                return True, None

            else:
                msg = data.get("msg", f"Erreur OBR {resp.status_code}")
                logger.warning(f"[OBR] Échec tentative {attempt}: {msg}")
                last_error = msg

        except requests.Timeout:
            last_error = f"Timeout après {TIMEOUT}s (tentative {attempt})"
            logger.warning(last_error)
        except requests.RequestException as e:
            last_error = f"Erreur réseau: {str(e)} (tentative {attempt})"
            logger.error(last_error)
        except ValueError as e:
            last_error = f"Erreur décodage JSON: {str(e)}"
            logger.error(last_error)
            break  # JSON invalide → pas la peine de réessayer
        except Exception as e:
            last_error = f"Erreur inattendue: {str(e)}"
            logger.exception(last_error)
            break

        if attempt < MAX_RETRIES:
            time.sleep(BASE_RETRY_DELAY * (1.5 ** (attempt - 1)))  # backoff exponentiel

    logger.error(f"[OBR] Échec définitif mouvement stock après {MAX_RETRIES} tentatives: {last_error}")
    return False, last_error





    def envoyer_mouvement_stock_automatique():
    """
    Envoie automatiquement tous les mouvements de stock en attente vers l'OBR.
    À appeler après chaque ajout de ligne ou via Celery périodiquement.
    """
    from .obr_service import get_obr_token  # on réutilise ton système de token

    token = get_obr_token()  # fonction que tu dois avoir dans obr_service.py
    if not token:
        logger.error("Impossible d'obtenir le token OBR pour les mouvements de stock")
        return

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    url = "https://ebms.obr.gov.bi:9443/ebms_api/AddStockMovement/"

    # === ENVOI DES ENTREES STOCK ===
    entrees_en_attente = EntreeStock.objects.filter(statut_obr='EN_ATTENTE')
    for entree in entrees_en_attente:
        try:
            payload = {
                "system_or_device_id": "ws" + str(entree.societe.id).zfill(12),  # à adapter selon ton system_id
                "item_code": entree.produit.code,
                "item_designation": entree.produit.designation,
                "item_quantity": float(entree.quantite),
                "item_measurement_unit": entree.produit.unite,
                "item_cost_price": float(entree.prix_revient),
                "item_cost_price_currency": entree.produit.devise,
                "item_movement_type": entree.type_entree,          # EN, ER, EI, etc.
                "item_movement_invoice_ref": "",                   # à remplir si besoin
                "item_movement_description": entree.commentaire or "",
                "item_movement_date": entree.date_entree.strftime("%Y-%m-%d %H:%M:%S")
            }

            response = requests.post(url, json=payload, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    entree.statut_obr = 'ENVOYE'
                    entree.date_envoi_obr = timezone.now()
                    entree.message_obr = data.get('msg', 'Envoyé avec succès')
                    entree.save()
                    logger.info(f"Entrée stock {entree.pk} envoyée avec succès à OBR")
                else:
                    entree.statut_obr = 'ECHEC'
                    entree.message_obr = data.get('msg', 'Erreur OBR')
                    entree.save()
            else:
                entree.statut_obr = 'ECHEC'
                entree.message_obr = f"HTTP {response.status_code}"
                entree.save()

        except Exception as e:
            logger.error(f"Erreur envoi entrée stock {entree.pk}: {e}")
            entree.statut_obr = 'ECHEC'
            entree.message_obr = str(e)[:200]
            entree.save()

    # === ENVOI DES SORTIES STOCK ===
    sorties_en_attente = SortieStock.objects.filter(statut_obr='EN_ATTENTE')
    for sortie in sorties_en_attente:
        try:
            payload = {
                "system_or_device_id": "ws" + str(sortie.societe.id).zfill(12),
                "item_code": sortie.produit.code,
                "item_designation": sortie.produit.designation,
                "item_quantity": float(sortie.quantite),
                "item_measurement_unit": sortie.produit.unite,
                "item_cost_price": float(sortie.prix),
                "item_cost_price_currency": "BIF",
                "item_movement_type": sortie.type_sortie,   # SN, SP, etc.
                "item_movement_invoice_ref": "", 
                "item_movement_description": sortie.commentaire or "",
                "item_movement_date": sortie.date_sortie.strftime("%Y-%m-%d %H:%M:%S")
            }

            response = requests.post(url, json=payload, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    sortie.statut_obr = 'ENVOYE'
                    sortie.date_envoi_obr = timezone.now()
                    sortie.message_obr = data.get('msg', 'Envoyé avec succès')
                    sortie.save()
                else:
                    sortie.statut_obr = 'ECHEC'
                    sortie.message_obr = data.get('msg', '')
                    sortie.save()
            else:
                sortie.statut_obr = 'ECHEC'
                sortie.message_obr = f"HTTP {response.status_code}"
                sortie.save()

        except Exception as e:
            logger.error(f"Erreur envoi sortie stock {sortie.pk}: {e}")
            sortie.statut_obr = 'ECHEC'
            sortie.message_obr = str(e)[:200]
            sortie.save()
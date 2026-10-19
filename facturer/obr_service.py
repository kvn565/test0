import requests
import logging
import time
from decimal import Decimal, ROUND_DOWN

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
CACHE_TOKEN_TIMEOUT = 2700

VERIFY_CERT = not settings.DEBUG
if not VERIFY_CERT:
    logger.warning("⚠️ VERIFY_CERT désactivé → Mode développement uniquement !")

ENDPOINT_LOGIN = "/login/"
ENDPOINT_ADD_INVOICE = "/addInvoice_confirm/"
ENDPOINT_CANCEL_INVOICE = "/cancelInvoice/"


# ─── TRONCATURE STRICTE 3 DÉCIMALES ─────────────────────────────────────
def truncate3(value):
    """Tronque strictement à 3 décimales SANS AUCUN ARRONDISSEMENT"""
    if value is None:
        return Decimal('0.000')
    try:
        dec = Decimal(str(value).strip())
        return dec.quantize(Decimal('0.001'), rounding=ROUND_DOWN)
    except:
        logger.warning(f"Impossible de convertir en Decimal: {value}")
        return Decimal('0.000')


# ─── URL & TOKEN (inchangé) ─────────────────────────────────────────────
def get_obr_base_url(societe):
    url = getattr(societe, 'obr_base_url', None)
    if url and str(url).strip():
        return str(url).strip().rstrip('/')
    host = "ebms.obr.gov.bi"
    port = 8443 if getattr(societe, 'obr_mode_production', False) else 9443
    return f"https://{host}:{port}/ebms_api"


def get_obr_headers(societe):
    return {
        "Authorization": f"Bearer {get_obr_token(societe)}",
        "Content-Type": "application/json"
    }


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


# ─── PAYLOAD (3 décimales partout) ─────────────────────────────────────
def build_invoice_payload(facture):
    if not facture.invoice_identifier:
        facture.generate_invoice_identifier()
        facture.save(update_fields=['invoice_identifier'])

    societe = facture.societe
    client = facture.client
    lignes = facture.lignes.select_related('produit', 'service', 'taux_tva').all()

    # Date
    try:
        date_part = facture.invoice_identifier.split('/')[2]
        y, m, d = date_part[0:4], date_part[4:6], date_part[6:8]
        h, min_, s = date_part[8:10], date_part[10:12], date_part[12:14]
        invoice_date_str = f"{y}-{m}-{d} {h}:{min_}:{s}"
    except:
        invoice_date_str = timezone.localtime().strftime("%Y-%m-%d %H:%M:%S")

    payment_mapping = {'CAISSE': '1', 'BANQUE': '2', 'CREDIT': '3', 'AUTRES': '4'}
    payment_type_obr = payment_mapping.get(facture.mode_paiement, '1')

    payload = {
        "invoice_number": str(facture.numero_obr)[:30],
        "invoice_date": invoice_date_str,
        "invoice_type": str(facture.type_facture)[:2],
        "tp_type": societe.get_tp_type(),
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
        "tp_fiscal_center": societe.get_tp_fiscal_center(),
        "tp_activity_sector": str(getattr(societe, 'secteur', 'SERVICE MARCHAND'))[:250],
        "tp_legal_form": str(getattr(societe, 'forme', 'SARL'))[:50],
        "payment_type": payment_type_obr,
        "invoice_currency": str(facture.devise)[:5],
        "customer_name": client.nom,
        "customer_TIN": getattr(client, 'nif', ''),
        "customer_address": str(getattr(client, 'adresse_complete', ''))[:100],
        "vat_customer_payer": "1" if getattr(client, 'assujeti_tva', False) else "0",
        "cancelled_invoice_ref": "",
        "invoice_ref": "",
        "cn_motif": "",
        "invoice_identifier": facture.invoice_identifier,
        "invoice_items": []
    }

    if facture.type_facture in ['FA', 'RC'] and facture.facture_originale:
        payload["invoice_ref"] = facture.facture_originale.numero[:30]
        payload["cn_motif"] = (facture.motif_avoir or "Avoir / Note de crédit")[:500]

    # Lignes avec 3 décimales strictes (spec EBMS: nvat=(PUxQ)+TC, vat=nvat*taux, wvat=nvat+vat, total=wvat+PFL)
    assujetti_tc = getattr(societe, 'assujeti_tc', False)
    assujetti_pfl = getattr(societe, 'assujeti_pfl', False)
    for ligne in lignes:
        prix_ht = truncate3(getattr(ligne, 'prix_unitaire_ht', 0))
        quantite = truncate3(ligne.quantite or 0)
        taux = truncate3(getattr(ligne.taux_tva, 'valeur', 0))

        montant_ht_base = truncate3(prix_ht * quantite)
        item_ct = truncate3(getattr(ligne, 'montant_ct', 0) or 0) if assujetti_tc else Decimal('0.000')
        item_tl = truncate3(getattr(ligne, 'montant_tl', 0) or 0) if assujetti_pfl else Decimal('0.000')
        montant_ht = truncate3(montant_ht_base + item_ct)
        montant_tva = truncate3(montant_ht * taux / Decimal('100'))
        montant_ttc = truncate3(montant_ht + montant_tva)
        montant_total = truncate3(montant_ttc + item_tl)

        payload["invoice_items"].append({
            "item_designation": str(ligne.designation)[:500],
            "item_quantity": str(quantite),
            "item_price": str(prix_ht),
            "item_ct": str(item_ct),
            "item_tl": str(item_tl),
            "item_ott_tax": "0",
            "item_tsce_tax": "0",
            "item_price_nvat": str(montant_ht),
            "vat": str(montant_tva),
            "item_price_wvat": str(montant_ttc),
            "item_total_amount": str(montant_total),
        })

    return payload


# ─── ENVOI FACTURE ─────────────────────────────────────────────────────────
def envoyer_facture_obr(facture):
    societe = facture.societe
    pending, _ = FacturePendingOBR.objects.get_or_create(facture=facture)

    response_data = None
    offline_failure = False

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

                response_data = {
                    'status_code': resp.status_code,
                    'body': resp.text,
                    'headers': dict(resp.headers)
                }

                # Debug log
                logger.info(f"\n{'='*60}\n[OBR RESPONSE] Facture: {facture.numero} | Attempt: {attempt}\n{'='*60}")
                logger.info(f"Status: {resp.status_code}")
                logger.info(f"Body:\n{resp.text}")
                logger.info(f"{'='*60}\n")

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
                        raw_date = data.get("result", {}).get("invoice_registered_date", "")
                        if raw_date:
                            from datetime import datetime as dt_lib
                            try:
                                # ✅ Rendre le datetime aware pour éviter le warning naïf
                                # et le décalage de fuseau au stockage MySQL (USE_TZ actif).
                                facture.obr_registered_date = timezone.make_aware(
                                    dt_lib.strptime(raw_date, "%Y-%m-%d %H:%M:%S")
                                )
                            except (ValueError, TypeError):
                                pass
                        facture.obr_mode_envoye = societe.obr_mode_production
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

                            elif facture.type_facture == 'FA':
                                traiter_stock_pour_avoir(facture)
                        except Exception as stock_err:
                            logger.warning(f"Erreur synchro stock: {stock_err}")

                        return {
                            'success': True,
                            'message': data.get("msg", "Facture envoyée"),
                            'payload_sent': payload,
                            'obr_response': response_data
                        }

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
                offline_failure = True
                msg = f"Erreur réseau: {e}"
                logger.error(msg)
                pending.message = msg
                pending.save(update_fields=['message'])
                # Hors-ligne : on s'arrête tout de suite (pas de sleep/réessai),
                # la reprise se fera automatiquement au retour de la connexion.
                break

        if offline_failure:
            # Hors-ligne : garder EN_ATTENTE pour reprise automatique au retour internet
            facture.statut_obr = 'EN_ATTENTE'
            facture.message_obr = "Hors-ligne - en attente de réenvoi (connexion OBR indisponible)"
            facture.save(update_fields=['statut_obr', 'message_obr'])

            pending.statut = "PENDING_RETRY"
            pending.message = "Connexion OBR indisponible - sera retenté automatiquement"
            pending.save()

            logger.info(f"[OBR] Hors-ligne - facture mise en attente pour réessai auto : {pending.message}")
            return {
                'success': False,
                'offline': True,
                'message': f"Mise en attente pour réessai automatique : {pending.message}",
                'pending_retry': True,
                'offline': True,
                'payload_sent': payload,
                'obr_response': response_data
            }

        # Rejet OBR (internet présent mais refus) → comme avant : facture EN_ATTENTE, pending FAILED
        facture.statut_obr = 'EN_ATTENTE'
        facture.message_obr = f"Rejet OBR après {MAX_RETRIES} tentatives - enregistrement non envoyé"
        facture.save(update_fields=['statut_obr', 'message_obr'])

        # ✅ CORRECTION : on ne compte que les VRAIES tentatives en ligne échouées.
        # Les tentatives hors-ligne (ConnectionError) ne doivent PAS épuiser le
        # budget de reprise, sinon une facture cliquée plusieurs fois en mode avion
        # finirait marquée ECHEC définitif et ne serait plus jamais renvoyée.
        pending.retry_count = (pending.retry_count or 0) + 1
        pending.statut = "FAILED"
        pending.message = f"Rejet OBR après {MAX_RETRIES} tentatives"
        pending.save()

        logger.info(f"[OBR] Rejet OBR définitif - facture {facture.numero} non envoyée (pending FAILED)")
        return {
            'success': False,
            'message': f"Rejet OBR - la facture n'a pas pu être envoyée",
            'payload_sent': payload,
            'obr_response': response_data
        }

    except Exception as e:
        logger.exception(f"[OBR] Erreur critique facture {facture.numero}")
        # Tentative en ligne échouée : on comptabilise (sauf si c'était hors-ligne)
        if not offline_failure:
            pending.retry_count = (pending.retry_count or 0) + 1
        pending.statut = "FAILED"
        pending.message = str(e)[:500]
        pending.save()
        return {
            'success': False,
            'message': str(e),
            'payload_sent': payload if 'payload' in dir() else None,
            'obr_response': response_data
        }


def annuler_facture_obr(facture, motif: str):
    if not motif or not motif.strip():
        return {'success': False, 'message': "Motif obligatoire"}

    motif = motif.strip()[:500]
    societe = facture.societe

    try:
        if facture.statut_obr == 'ENVOYE':
            if not facture.invoice_identifier:
                return {'success': False, 'message': "invoice_identifier manquant"}

            base_url = get_obr_base_url(societe)
            url = f"{base_url}{ENDPOINT_CANCEL_INVOICE}"

            payload = {
                "invoice_identifier": facture.invoice_identifier,
                "cn_motif": motif
            }

            logger.info(f"[OBR] Annulation facture {facture.numero} | Société: {societe.nom}")

            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    resp = requests.post(
                        url, json=payload, headers=get_obr_headers(societe),
                        timeout=TIMEOUT, verify=VERIFY_CERT
                    )

                    if resp.status_code in (401, 403):
                        logger.warning(f"[OBR Cancel] Token invalide (tentative {attempt}) → refresh")
                        invalidate_obr_token(societe)
                        if attempt == MAX_RETRIES:
                            return {'success': False, 'message': "Token OBR invalide après plusieurs tentatives"}
                        continue

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

                    message_obr = "✓ OBR : " + (data.get("msg", "") or resp.text[:500])
                    break

                except requests.RequestException as e:
                    msg = f"Tentative {attempt} - Erreur réseau: {str(e)}"
                    logger.error(msg)
                    if attempt < MAX_RETRIES:
                        time.sleep(BASE_RETRY_DELAY)
                    else:
                        return {'success': False, 'message': msg}
        else:
            message_obr = f"Annulée localement - Motif : {motif}"

        with transaction.atomic():
            pending, _ = FacturePendingOBR.objects.get_or_create(facture=facture)

            facture.statut_obr = 'ANNULE'
            facture.message_obr = message_obr
            facture.motif_avoir = f"Annulation : {motif}"
            facture.date_annulation = timezone.now()

            facture.save(update_fields=['statut_obr', 'message_obr', 'motif_avoir', 'date_annulation'])

            # ===== RESTAURATION STOCK APRÈS ANNULATION OBR =====
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
                        if isinstance(result, (list, tuple)):
                            success, msg = result[0], result[1]
                        else:
                            success, msg = result.get('success', False), result.get('message', '')
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
                        if isinstance(result, (list, tuple)):
                            success, msg = result[0], result[1]
                        else:
                            success, msg = result.get('success', False), result.get('message', '')
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
                # Rejet OBR → ECHEC comme avant
                entree.statut_obr = 'ECHEC'
                entree.message_obr = msg or 'Échec envoi'
                entree.save(update_fields=['statut_obr', 'message_obr'])

        except requests.exceptions.RequestException as e:
            logger.error(f"[STOCK OFFLINE] Entrée ER {entree.pk} - gardée en attente : {e}", exc_info=True)
            # Hors-ligne → EN_ATTENTE pour reprise automatique
            entree.statut_obr = 'EN_ATTENTE'
            entree.message_obr = f"Hors-ligne - en attente de réenvoi : {str(e)[:100]}"
            entree.save(update_fields=['statut_obr', 'message_obr'])
        except Exception as e:
            logger.error(f"[STOCK] Erreur sur entrée ER {entree.pk}: {e}", exc_info=True)
            # Autre erreur → ECHEC comme avant
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
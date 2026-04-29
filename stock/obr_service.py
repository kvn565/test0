# stock/obr_service.py — VERSION FINALE
# API totalement dynamique par société (obr_base_url, username, password).

import requests
import logging
from datetime import timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)

TIMEOUT = 30

ENDPOINT_LOGIN             = "/login/"
ENDPOINT_ADD_STOCK_LOCAL   = "/AddStockMovement/"
ENDPOINT_ADD_STOCK_IMPORTE = "/AddStockMovementImporters/"


# ─── HELPERS DYNAMIQUES PAR SOCIÉTÉ ─────────────────────────────────────────
def get_obr_base_url(societe):
    """
    Retourne l'URL de base OBR de la société.
    Lève une ValueError explicite si non configurée.
    """
    url = getattr(societe, 'obr_base_url', None)
    if not url or not str(url).strip():
        raise ValueError(
            f"URL Base OBR non configurée pour la société '{societe}'. "
            f"Veuillez renseigner le champ obr_base_url."
        )
    return str(url).strip().rstrip('/')


def build_obr_url(societe, endpoint):
    """Construit l'URL complète OBR pour une société et un endpoint donnés."""
    return f"{get_obr_base_url(societe)}{endpoint}"


# ═══════════════════════════════════════════════════════════════════════
# UTILITAIRE APPEL API SÉCURISÉ
# ═══════════════════════════════════════════════════════════════════════
def _post_obr(url, payload, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT, verify=True)
    except requests.exceptions.RequestException as e:
        raise ConnectionError(f"Connexion OBR impossible : {e}")

    try:
        data = response.json()
    except ValueError:
        raise ConnectionError(f"Réponse OBR invalide (non JSON) - HTTP {response.status_code}")

    return response.status_code, data


# ═══════════════════════════════════════════════════════════════════════
# AUTHENTIFICATION
# ═══════════════════════════════════════════════════════════════════════
def get_token_obr(societe):
    """
    Authentification OBR dynamique par société.
    Utilise obr_base_url, obr_username, obr_password de la société.
    """
    username = getattr(societe, "obr_username", None)
    password = getattr(societe, "obr_password", None)

    if not username or not password:
        raise ValueError(
            f"Société '{societe}' : credentials OBR manquants (obr_username / obr_password)."
        )

    url = build_obr_url(societe, ENDPOINT_LOGIN)
    status, data = _post_obr(url, {"username": username, "password": password})

    if status == 200 and data.get("success"):
        return data["result"]["token"]

    raise ConnectionError(
        f"Échec authentification OBR pour '{societe}' : {data.get('msg', 'Erreur inconnue')}"
    )


# ═══════════════════════════════════════════════════════════════════════
# ENVOI ENTRÉE STOCK
# ═══════════════════════════════════════════════════════════════════════
def envoyer_entree_stock(entree):
    """Envoie une entrée stock (ER ou EN) à l'OBR avec heure GMT+2."""
    from .models import EntreeStock

    societe = entree.societe
    produit = entree.produit

    system_id = getattr(societe, "obr_system_id", "")
    if not system_id:
        return False, "system_id OBR non configuré."

    est_importe = getattr(produit, "origine", "").upper() == "IMPORTE"

    # URL dynamique par société + type de produit
    url = build_obr_url(
        societe,
        ENDPOINT_ADD_STOCK_IMPORTE if est_importe else ENDPOINT_ADD_STOCK_LOCAL
    )

    # Heure GMT+2 (Bujumbura)
    gmt_plus_2   = timezone.now() + timedelta(hours=2)
    date_mvt_str = gmt_plus_2.strftime("%Y-%m-%d %H:%M:%S")

    # Référence facture originale pour les retours ER (conforme doc OBR)
    invoice_ref = ""
    if (entree.type_entree == 'ER'
            and getattr(entree, 'facture', None)
            and getattr(entree.facture, 'facture_originale', None)):
        invoice_ref = str(entree.facture.facture_originale.numero or "")[:30]

    payload = {
        "system_or_device_id":       str(system_id).strip(),
        "item_code":                 str(produit.code or f"PROD-{produit.pk}")[:30],
        "item_designation":          str(produit.designation)[:500],
        "item_quantity":             float(entree.quantite),
        "item_measurement_unit":     str(produit.unite or 'unité')[:20],
        "item_cost_price":           float(entree.prix_revient or 0),
        "item_cost_price_currency":  "BIF",
        "item_movement_type":        str(entree.type_entree),
        "item_movement_invoice_ref": invoice_ref,
        "item_movement_description": str(entree.commentaire or f"Retour avoir {getattr(entree.facture, 'numero', '')}")[:500],
        "item_movement_date":        date_mvt_str
    }

    if est_importe:
        payload.update({
            "reference_dmc":      str(getattr(produit, "reference_dmc", "")),
            "rubrique_tarifaire": str(getattr(produit, "rubrique_tarifaire", "")),
            "nombre_par_paquet":  str(getattr(produit, "nombre_par_paquet", "1")),
            "description_paquet": str(getattr(produit, "description_paquet", "")),
        })

    try:
        token = get_token_obr(societe)
        status, data = _post_obr(url, payload, token)

        if status == 200 and data.get("success"):
            EntreeStock.objects.filter(pk=entree.pk).update(
                statut_obr="ENVOYE",
                message_obr=data.get("msg", "Envoyé avec succès"),
                date_envoi_obr=timezone.now(),
            )
            logger.info(f"[OBR] Entrée #{entree.pk} ({entree.type_entree}) envoyée | Société: {societe}")
            return True, data.get("msg", "")

        msg = data.get("msg", f"Erreur HTTP {status}")
        EntreeStock.objects.filter(pk=entree.pk).update(statut_obr="ECHEC", message_obr=msg)
        logger.warning(f"[OBR] Échec entrée #{entree.pk} | Société: {societe} : {msg}")
        return False, msg

    except Exception as e:
        EntreeStock.objects.filter(pk=entree.pk).update(statut_obr="ECHEC", message_obr=str(e)[:200])
        logger.error(f"[OBR] Exception entrée #{entree.pk} | Société: {societe} : {e}")
        return False, str(e)


# ═══════════════════════════════════════════════════════════════════════
# ENVOI SORTIE STOCK
# ═══════════════════════════════════════════════════════════════════════
def envoyer_sortie_stock(sortie):
    """Envoie une sortie stock à l'OBR avec heure GMT+2."""
    from .models import SortieStock

    societe = sortie.societe
    produit = sortie.produit

    system_id = getattr(societe, "obr_system_id", "")
    if not system_id:
        return False, "system_id OBR non configuré."

    # URL dynamique par société (sorties toujours sur le endpoint local)
    url = build_obr_url(societe, ENDPOINT_ADD_STOCK_LOCAL)

    # Heure GMT+2 (Bujumbura)
    gmt_plus_2   = timezone.now() + timedelta(hours=2)
    date_mvt_str = gmt_plus_2.strftime("%Y-%m-%d %H:%M:%S")

    payload = {
        "system_or_device_id":       str(system_id).strip(),
        "item_code":                 str(produit.code or f"PROD-{produit.pk}")[:30],
        "item_designation":          str(produit.designation)[:500],
        "item_quantity":             float(sortie.quantite),
        "item_measurement_unit":     str(produit.unite or 'unité')[:20],
        "item_cost_price":           float(sortie.prix or 0),
        "item_cost_price_currency":  "BIF",
        "item_movement_type":        str(sortie.type_sortie),
        "item_movement_invoice_ref": "",
        "item_movement_description": str(sortie.commentaire or f"Vente facture {getattr(sortie.facture, 'numero', '')}")[:500],
        "item_movement_date":        date_mvt_str
    }

    try:
        token = get_token_obr(societe)
        status, data = _post_obr(url, payload, token)

        if status == 200 and data.get("success"):
            SortieStock.objects.filter(pk=sortie.pk).update(
                statut_obr="ENVOYE",
                message_obr=data.get("msg", "Envoyé avec succès"),
                date_envoi_obr=timezone.now(),
            )
            logger.info(f"[OBR] Sortie #{sortie.pk} envoyée | Société: {societe}")
            return True, data.get("msg", "")

        msg = data.get("msg", f"Erreur HTTP {status}")
        SortieStock.objects.filter(pk=sortie.pk).update(statut_obr="ECHEC", message_obr=msg)
        logger.warning(f"[OBR] Échec sortie #{sortie.pk} | Société: {societe} : {msg}")
        return False, msg

    except Exception as e:
        SortieStock.objects.filter(pk=sortie.pk).update(statut_obr="ECHEC", message_obr=str(e)[:200])
        logger.error(f"[OBR] Exception sortie #{sortie.pk} | Société: {societe} : {e}")
        return False, str(e)

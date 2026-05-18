import requests
import logging
from zoneinfo import ZoneInfo
from django.utils import timezone
from django.db import transaction

logger = logging.getLogger(__name__)

TIMEOUT = 30

# Endpoints OBR
ENDPOINT_LOGIN             = "/login/"
ENDPOINT_ADD_STOCK_LOCAL   = "/AddStockMovement/"
ENDPOINT_ADD_STOCK_IMPORTE = "/AddStockMovementImporters/"


# ====================== HELPERS ======================
def get_obr_base_url(societe):
    """Retourne l'URL de base OBR de la société"""
    url = getattr(societe, 'obr_base_url', None)
    if not url or not str(url).strip():
        raise ValueError(
            f"URL Base OBR non configurée pour la société '{societe}'. "
            "Veuillez renseigner le champ obr_base_url dans l'administration."
        )
    return str(url).strip().rstrip('/')


def build_obr_url(societe, endpoint):
    """Construit l'URL complète"""
    return f"{get_obr_base_url(societe)}{endpoint}"


def get_obr_datetime():
    """Retourne la date/heure au format OBR (GMT+2 - Bujumbura)"""
    bujumbura_tz = ZoneInfo("Africa/Bujumbura")
    now_buj = timezone.now().astimezone(bujumbura_tz)
    return now_buj.strftime("%Y-%m-%d %H:%M:%S")


# ====================== VÉRIFICATION CONFIGURATION ======================
def check_obr_configuration(societe):
    """
    Vérifie si l'OBR est bien configuré.
    Retourne (success: bool, message: str)
    """
    if not getattr(societe, 'obr_actif', False):
        return False, "Intégration OBR désactivée pour cette société."

    if not getattr(societe, 'obr_base_url', None):
        return False, "URL Base OBR non configurée."

    if not getattr(societe, 'obr_username', None) or not getattr(societe, 'obr_password', None):
        return False, "Nom d'utilisateur ou mot de passe OBR manquant."

    if not getattr(societe, 'obr_system_id', None):
        return False, "System ID OBR non configuré."

    return True, "Configuration OBR valide"


# ====================== APPEL API ======================
def _post_obr(url, payload, token=None):
    """Fonction utilitaire sécurisée pour les requêtes POST vers l'OBR"""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        response = requests.post(url, json=payload, headers=headers, 
                               timeout=TIMEOUT, verify=True)
        
        try:
            data = response.json()
        except ValueError:
            data = {"msg": response.text[:300] if response.text else "Réponse invalide"}

        return response.status_code, data

    except requests.exceptions.RequestException as e:
        raise ConnectionError(f"Connexion OBR impossible : {e}")


# ====================== AUTHENTIFICATION ======================
def get_token_obr(societe):
    """Récupère le token Bearer pour une société"""
    username = getattr(societe, "obr_username", "").strip()
    password = getattr(societe, "obr_password", "").strip()

    if not username or not password:
        raise ValueError(f"Credentials OBR manquants pour la société '{societe}'.")

    url = build_obr_url(societe, ENDPOINT_LOGIN)
    status, data = _post_obr(url, {"username": username, "password": password})

    if status == 200 and data.get("success"):
        return data["result"]["token"]

    raise ConnectionError(
        f"Échec authentification OBR pour '{societe}' : {data.get('msg', 'Erreur inconnue')}"
    )


# ====================== ENVOI ENTRÉE STOCK ======================
def envoyer_entree_stock(entree):
    """Envoie une entrée en stock vers l'OBR"""
    from .models import EntreeStock

    societe = entree.societe

    # ====================== NOUVEAU : VÉRIFICATION CONFIGURATION ======================
    configured, config_msg = check_obr_configuration(societe)
    if not configured:
        # Supprimer l'enregistrement pour ne pas laisser de mouvement "en attente"
        with transaction.atomic():
            EntreeStock.objects.filter(pk=entree.pk).delete()
        return False, f"❌ {config_msg} Veuillez configurer l'OBR dans l'administration."

    # Si déjà traité
    if entree.statut_obr != 'EN_ATTENTE':
        return True, "Déjà traité"

    system_id = getattr(societe, "obr_system_id", "").strip()
    if not system_id:
        with transaction.atomic():
            EntreeStock.objects.filter(pk=entree.pk).delete()
        return False, "System ID OBR non configuré. Enregistrement supprimé."

    produit = entree.produit
    est_importe = getattr(produit, "origine", "").upper() == "IMPORTE"

    endpoint = ENDPOINT_ADD_STOCK_IMPORTE if est_importe else ENDPOINT_ADD_STOCK_LOCAL
    url = build_obr_url(societe, endpoint)

    invoice_ref = ""
    if (entree.type_entree == 'ER' and 
        getattr(entree, 'facture', None) and 
        getattr(entree.facture, 'facture_originale', None)):
        invoice_ref = str(entree.facture.facture_originale.numero or "")[:30]

    payload = {
        "system_or_device_id":       str(system_id),
        "item_code":                 str(produit.code or f"PROD-{produit.pk}")[:30],
        "item_designation":          str(produit.designation)[:500],
        "item_quantity":             float(entree.quantite),
        "item_measurement_unit":     str(produit.unite or 'unité')[:20],
        "item_cost_price":           float(getattr(entree, 'prix_revient', 0) or 0),
        "item_cost_price_currency":  "BIF",
        "item_movement_type":        str(entree.type_entree),
        "item_movement_invoice_ref": invoice_ref,
        "item_movement_description": str(entree.commentaire or f"Entrée stock {entree.type_entree}")[:500],
        "item_movement_date":        get_obr_datetime(),
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
            logger.info(f"[OBR SUCCESS] Entrée #{entree.pk} ({entree.type_entree}) - {societe}")
            return True, data.get("msg", "Succès")

        # ====================== ÉCHEC : On supprime ======================
        msg = data.get("msg", f"Erreur HTTP {status}")
        logger.warning(f"[OBR FAILED] Entrée #{entree.pk} → Suppression automatique")
        
        with transaction.atomic():
            EntreeStock.objects.filter(pk=entree.pk).delete()
        
        return False, f"Échec OBR - Enregistrement supprimé ({msg})"

    except Exception as e:
        logger.error(f"[OBR EXCEPTION] Entrée #{entree.pk} → Suppression automatique")
        with transaction.atomic():
            EntreeStock.objects.filter(pk=entree.pk).delete()
        return False, f"Erreur technique - Enregistrement supprimé ({str(e)[:100]})"


# ====================== ENVOI SORTIE STOCK ======================
def envoyer_sortie_stock(sortie):
    """Envoie une sortie stock vers l'OBR"""
    from .models import SortieStock

    societe = sortie.societe

    # Vérification configuration
    configured, config_msg = check_obr_configuration(societe)
    if not configured:
        with transaction.atomic():
            SortieStock.objects.filter(pk=sortie.pk).delete()
        return False, f"❌ {config_msg} Veuillez configurer l'OBR dans l'administration."

    if sortie.statut_obr != 'EN_ATTENTE':
        return True, "Déjà traité"

    system_id = getattr(societe, "obr_system_id", "").strip()
    if not system_id:
        with transaction.atomic():
            SortieStock.objects.filter(pk=sortie.pk).delete()
        return False, "System ID OBR non configuré. Enregistrement supprimé."

    produit = sortie.produit
    url = build_obr_url(societe, ENDPOINT_ADD_STOCK_LOCAL)

    payload = {
        "system_or_device_id":       str(system_id),
        "item_code":                 str(produit.code or f"PROD-{produit.pk}")[:30],
        "item_designation":          str(produit.designation)[:500],
        "item_quantity":             float(sortie.quantite),
        "item_measurement_unit":     str(produit.unite or 'unité')[:20],
        "item_cost_price":           float(getattr(sortie, 'prix', 0) or 0),
        "item_cost_price_currency":  "BIF",
        "item_movement_type":        str(sortie.type_sortie),
        "item_movement_invoice_ref": "",
        "item_movement_description": str(sortie.commentaire or f"Sortie stock {sortie.type_sortie}")[:500],
        "item_movement_date":        get_obr_datetime(),
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
            logger.info(f"[OBR SUCCESS] Sortie #{sortie.pk} - {societe}")
            return True, data.get("msg", "Succès")

        msg = data.get("msg", f"Erreur HTTP {status}")
        logger.warning(f"[OBR FAILED] Sortie #{sortie.pk} → Suppression automatique")
        
        with transaction.atomic():
            SortieStock.objects.filter(pk=sortie.pk).delete()
        
        return False, f"Échec OBR - Enregistrement supprimé ({msg})"

    except Exception as e:
        logger.error(f"[OBR EXCEPTION] Sortie #{sortie.pk} → Suppression automatique")
        with transaction.atomic():
            SortieStock.objects.filter(pk=sortie.pk).delete()
        return False, f"Erreur technique - Enregistrement supprimé ({str(e)[:100]})"


def nettoyer_avant_nouvelle_entree(societe, produit=None, type_entree=None):
    """
    Nettoie automatiquement les anciens mouvements en attente ou en échec
    avant de créer une nouvelle entrée stock.
    """
    with transaction.atomic():
        # Nettoyage Entrées
        qs_entrees = EntreeStock.objects.filter(
            societe=societe,
            statut_obr__in=['EN_ATTENTE', 'ECHEC']
        )
        
        # Optionnel : filtrer par produit
        if produit:
            qs_entrees = qs_entrees.filter(produit=produit)

        # Nettoyage Sorties
        qs_sorties = SortieStock.objects.filter(
            societe=societe,
            statut_obr__in=['EN_ATTENTE', 'ECHEC']
        )

        deleted_entrees = qs_entrees.count()
        deleted_sorties = qs_sorties.count()

        # Suppression
        qs_entrees.delete()
        qs_sorties.delete()

        if deleted_entrees > 0 or deleted_sorties > 0:
            print(f"🧹 Nettoyage automatique : {deleted_entrees} entrées + {deleted_sorties} sorties supprimées")

        return {
            'entrees_supprimees': deleted_entrees,
            'sorties_supprimees': deleted_sorties
        }


def nettoyer_avant_nouvelle_sortie(societe, entree_stock=None):
    """Même fonction mais pour les sorties"""
    with transaction.atomic():
        qs = SortieStock.objects.filter(
            societe=societe,
            statut_obr__in=['EN_ATTENTE', 'ECHEC']
        )
        
        if entree_stock:
            qs = qs.filter(entree_stock=entree_stock)

        count = qs.count()
        qs.delete()

        if count > 0:
            print(f"🧹 {count} sorties en attente/échec supprimées")
        
        return count
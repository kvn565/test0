# clients/utils/obr_api.py
import requests
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

ENDPOINT_LOGIN     = "/login/"
ENDPOINT_CHECK_TIN = "/checkTIN/"


# ─── HELPERS DYNAMIQUES PAR SOCIÉTÉ ─────────────────────────────────

def get_obr_base_url(societe) -> str:
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


def build_obr_url(societe, endpoint: str) -> str:
    """Construit l'URL complète OBR pour une société et un endpoint donnés."""
    return f"{get_obr_base_url(societe)}{endpoint}"


# ═══════════════════════════════════════════════════════════════════════
# AUTHENTIFICATION
# ═══════════════════════════════════════════════════════════════════════

def get_ebms_token(societe) -> Optional[str]:
    """
    Récupère un token JWT OBR valide.
    URL dynamique par société via obr_base_url.
    """
    if not societe.obr_username or not societe.obr_password:
        return None

    url = build_obr_url(societe, ENDPOINT_LOGIN)

    payload = {
        "username": societe.obr_username,
        "password": societe.obr_password
    }

    try:
        response = requests.post(url, json=payload, timeout=8)
        response.raise_for_status()
        data = response.json()
        if data.get("success") and "result" in data and "token" in data["result"]:
            return data["result"]["token"]
    except Exception as e:
        logger.error(f"[OBR] Erreur login pour '{societe}' : {e}")

    return None


# ═══════════════════════════════════════════════════════════════════════
# VÉRIFICATION NIF
# ═══════════════════════════════════════════════════════════════════════

def check_tin(societe, nif: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Vérifie un NIF via l'API OBR /checkTIN/.
    URL dynamique par société via obr_base_url.
    Retourne (nom_officiel, None) en cas de succès
    ou (None, message_erreur) en cas d'échec.
    """
    token = get_ebms_token(societe)
    if not token:
        return None, (
            "Impossible d'obtenir un token OBR. "
            "Vérifiez les identifiants (obr_username / obr_password) et l'URL (obr_base_url) dans la fiche société."
        )

    url = build_obr_url(societe, ENDPOINT_CHECK_TIN)

    headers = {"Authorization": f"Bearer {token}"}
    payload = {"tp_TIN": nif.strip()}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=8)
        response.raise_for_status()
        data = response.json()

        if data.get("success") and data.get("result", {}).get("taxpayer"):
            taxpayer = data["result"]["taxpayer"][0]
            nom = taxpayer.get("tp_name", "").strip()
            if nom:
                return nom, None
            return None, "Nom non retourné par l'OBR"

        return None, data.get("msg", "Réponse inattendue de l'OBR")

    except requests.exceptions.RequestException as e:
        logger.error(f"[OBR] Erreur checkTIN pour '{societe}' : {e}")
        return None, f"Erreur réseau lors de la vérification NIF : {str(e)}"

    except Exception as e:
        logger.error(f"[OBR] Erreur inattendue checkTIN pour '{societe}' : {e}")
        return None, f"Erreur inattendue : {str(e)}"

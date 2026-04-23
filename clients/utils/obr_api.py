# clients/utils/obr_api.py
import requests
from django.conf import settings
from typing import Tuple, Optional

EBMS_BASE_URL = "https://ebms.obr.gov.bi:9443/ebms_api"


def get_ebms_token(societe) -> Optional[str]:
    """
    Récupère un token JWT valide (durée de vie ~60 secondes)
    """
    if not societe.obr_username or not societe.obr_password:
        return None

    url = f"{EBMS_BASE_URL}/login/"
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
        print(f"Erreur login OBR : {e}")  # ← pour debug, à retirer en prod
        pass

    return None


def check_tin(societe, nif: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Vérifie un NIF via l'API OBR /checkTIN/
    Retourne (nom_officiel, None) en cas de succès
    ou (None, message_erreur) en cas d'échec
    """
    token = get_ebms_token(societe)
    if not token:
        return None, "Impossible d'obtenir un token OBR. Vérifiez les identifiants (obr_username / obr_password) dans la fiche société."

    url = f"{EBMS_BASE_URL}/checkTIN/"
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
        print(f"Erreur checkTIN : {e}")  # ← debug
        return None, f"Erreur réseau lors de la vérification NIF : {str(e)}"
    except Exception as e:
        print(f"Erreur inattendue checkTIN : {e}")
        return None, f"Erreur inattendue : {str(e)}"
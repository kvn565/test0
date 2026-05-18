import requests
import urllib3
from decimal import Decimal
from django.core.cache import cache
from taux.models import TauxTVA

# Désactive les warnings SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ─── ENDPOINTS ──────────────────────────────────────────────────────
ENDPOINT_LOGIN        = "/login/"
ENDPOINT_GET_DMC      = "/getDmcItems/"

TOKEN_CACHE_SECONDS = 50


def get_obr_base_url(societe):
    url = getattr(societe, 'obr_base_url', None)
    if not url or not str(url).strip():
        raise ValueError(
            f"URL Base OBR non configurée pour la société '{societe.nom}'. "
            f"Veuillez configurer le champ 'obr_base_url' dans l'administration."
        )
    return str(url).strip().rstrip('/')


def build_obr_url(societe, endpoint):
    return f"{get_obr_base_url(societe)}{endpoint}"


class OBRService:

    @staticmethod
    def _get_token(societe):
        cache_key = f"obr_token_{societe.pk}"
        token = cache.get(cache_key)
        if token:
            return token

        url = build_obr_url(societe, ENDPOINT_LOGIN)

        username = getattr(societe, 'obr_username', None)
        password = getattr(societe, 'obr_password', None)
        system_id = getattr(societe, 'obr_system_id', None)

        if not username or not str(username).strip():
            raise ValueError("OBR Username non configuré pour cette société.")
        if not password or not str(password).strip():
            raise ValueError("OBR Password non configuré pour cette société.")
        if not system_id or not str(system_id).strip():
            raise ValueError("OBR System ID non configuré pour cette société.")

        body = {
            "username": str(username).strip(),
            "password": str(password).strip(),
        }

        response = requests.post(
            url, json=body, headers={"Content-Type": "application/json"},
            timeout=10, verify=False
        )

        if not response.ok:
            msg = OBRService._extract_obr_message(response)
            raise Exception(f"Connexion OBR échouée [HTTP {response.status_code}] : {msg}")

        data = response.json()
        if not data.get("success"):
            raise Exception(f"Connexion OBR échouée : {data.get('msg', 'Erreur inconnue')}")

        token = data.get("result", {}).get("token")
        if not token:
            raise Exception("Token non reçu de l'OBR.")

        cache.set(cache_key, token, timeout=TOKEN_CACHE_SECONDS)
        return token

    @staticmethod
    def _extract_obr_message(response):
        """Extrait proprement le message d'erreur de l'API OBR"""
        try:
            data = response.json()
            return data.get('msg') or data.get('message') or response.text[:300]
        except Exception:
            return response.text[:300] or "Erreur inconnue de l'OBR"

    @staticmethod
    def _get_taux_tva(societe):
        """
        Retourne l'objet TauxTVA à utiliser pour l'import OBR.
        Utilise la logique métier définie dans TauxTVAManager.
        """
        try:
            # Utilisation de la méthode métier que vous avez déjà créée
            taux_obj = TauxTVA.objects.resolve_for_obr(societe)
            if taux_obj:
                return taux_obj

            # Fallback sur le taux par défaut
            taux_obj = TauxTVA.objects.get_taux_defaut(societe)
            if taux_obj:
                return taux_obj

            # Dernier recours
            return (
                TauxTVA.objects.filter(societe=societe, valeur=Decimal('0.18')).first() or
                TauxTVA.objects.filter(societe=societe).order_by('-valeur').first() or
                TauxTVA.objects.filter(societe=societe, valeur=Decimal('0.00')).first()
            )

        except Exception as e:
            print(f"[OBRService._get_taux_tva] Erreur : {e}")
            # Sécurité : toujours retourner quelque chose
            return TauxTVA.objects.filter(societe=societe, valeur=Decimal('0.00')).first()

    @staticmethod
    def get_dmc_info(societe, reference_dmc):
        """
        Récupère les informations DMC depuis l'OBR.
        """
        try:
            token = OBRService._get_token(societe)
        except ValueError as e:
            raise Exception(str(e)) from e
        except Exception as e:
            raise Exception(f"Impossible de se connecter à l'OBR : {str(e)}") from e

        url = build_obr_url(societe, ENDPOINT_GET_DMC)

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        payload = {
            "nif": str(societe.nif).strip(),
            "reference_dmc": str(reference_dmc).strip(),
        }

        response = requests.post(
            url, json=payload, headers=headers, timeout=15, verify=False
        )

        if not response.ok:
            msg_obr = OBRService._extract_obr_message(response)
            raise Exception(f"OBR getDmcItems [HTTP {response.status_code}] : {msg_obr}")

        data = response.json()

        if not data.get("success"):
            msg = data.get("msg") or "Erreur retournée par l'OBR"
            raise Exception(msg)

        result = data.get("result", {})
        items = result.get("items", [])

        if not items:
            raise Exception("La référence DMC n'appartient pas à ce NIF. Vérifiez que vous utilisez le bon compte société.")

        item = items[0]
        taux_obj = OBRService._get_taux_tva(societe)

        return {
            "code":               reference_dmc,
            "designation":        item.get("description_article", ""),
            "rubrique_tarifaire": item.get("rubrique_tarifaire", ""),
            "nombre_par_paquet":  item.get("quantite", ""),
            "description_paquet": item.get("description_packet", ""),
            "unite":              "Pièce",
            "taux_tva":           taux_obj.pk if taux_obj else None,
            "reference_dmc":      result.get("reference_dmc", reference_dmc),
        }
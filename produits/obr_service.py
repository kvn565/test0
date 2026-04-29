# produits/obr_service.py
import requests
from django.core.cache import cache

ENDPOINT_LOGIN    = "/login/"
ENDPOINT_GET_DMC  = "/getDmcItems/"


# ─── HELPERS DYNAMIQUES PAR SOCIÉTÉ ─────────────────────────────────

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


class OBRService:

    @staticmethod
    def _get_token(societe):
        """Récupère ou rafraîchit le token OBR (mis en cache 50 minutes), isolé par société."""
        cache_key = f"obr_token_{societe.pk}"
        token = cache.get(cache_key)
        if token:
            return token

        url = build_obr_url(societe, ENDPOINT_LOGIN)

        data = {
            "username": societe.obr_username,
            "password": societe.obr_password
        }

        response = requests.post(url, json=data, timeout=10)
        response.raise_for_status()
        result = response.json()

        if result.get("success"):
            token = result["result"]["token"]
            cache.set(cache_key, token, timeout=3000)  # 50 minutes
            return token

        raise Exception(f"OBR Login failed pour '{societe}' : {result.get('msg')}")

    @staticmethod
    def get_dmc_info(societe, reference_dmc):
        """
        Récupère les données DMC depuis OBR et les formate pour le formulaire Produit.
        URL dynamique par société via obr_base_url.
        """
        token = OBRService._get_token(societe)

        url = build_obr_url(societe, ENDPOINT_GET_DMC)

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        payload = {
            "nif": societe.nif,
            "reference_dmc": reference_dmc.strip()
        }

        response = requests.post(url, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()

        if not data.get("success"):
            error_msg = data.get("msg") or "Aucune donnée trouvée pour ce DMC"
            raise Exception(error_msg)

        result = data.get("result", {})
        items = result.get("items", [])

        if not items:
            raise Exception("La reference DMC n'appartient pas a ce NIF")

        item = items[0]

        return {
            "code": reference_dmc,
            "designation": item.get("description_article", ""),
            "rubrique_tarifaire": item.get("rubrique_tarifaire", ""),
            "nombre_par_paquet": item.get("quantite", ""),
            "description_paquet": item.get("description_packet", ""),
            "unite": "Pièce",
            "taux_tva": 18,
            "reference_dmc": result.get("reference_dmc", reference_dmc),
        }

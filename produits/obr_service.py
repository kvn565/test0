# produits/obr_service.py
import requests
from django.core.cache import cache

class OBRService:
    BASE_URL = "https://ebms.obr.gov.bi:9443/ebms_api"

    @staticmethod
    def _get_token(societe):
        """Récupère ou rafraîchit le token (mis en cache 50 minutes)"""
        cache_key = f"obr_token_{societe.pk}"
        token = cache.get(cache_key)

        if token:
            return token

        url = f"{OBRService.BASE_URL}/login/"
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

        raise Exception(f"OBR Login failed: {result.get('msg')}")


    @staticmethod
    def get_dmc_info(societe, reference_dmc):
        """
        Récupère les données DMC depuis OBR et les formate pour le formulaire Produit
        """
        token = OBRService._get_token(societe)

        url = f"{OBRService.BASE_URL}/getDmcItems/"

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

        # === CORRECTION : Gestion du message exact quand la référence n'appartient pas au NIF ===
        if not data.get("success"):
            # On récupère et on renvoie le message exact de l'OBR
            error_msg = data.get("msg") or "Aucune donnée trouvée pour ce DMC"
            raise Exception(error_msg)

        result = data.get("result", {})
        items = result.get("items", [])

        # Si la liste items est vide → référence DMC invalide pour ce NIF
        if not items:
            raise Exception("La reference DMC n'appartient pas a ce NIF")

        item = items[0]

        # Retour formaté pour remplir directement les champs du formulaire
        return {
            "code": reference_dmc,                                   # Code produit = Référence DMC
            "designation": item.get("description_article", ""),      # Désignation
            "rubrique_tarifaire": item.get("rubrique_tarifaire", ""),
            "nombre_par_paquet": item.get("quantite", ""),           # Quantité = nombre par paquet
            "description_paquet": item.get("description_packet", ""),
            "unite": "Pièce",                                        # Valeur par défaut
            "taux_tva": 18,                                          # Valeur par défaut
            "reference_dmc": result.get("reference_dmc", reference_dmc),
        }
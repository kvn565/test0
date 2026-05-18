import requests
import urllib3
from decimal import Decimal
from django.core.cache import cache
from taux.models import TauxTVA

# Désactive les warnings SSL (serveur OBR utilise parfois un cert auto-signé)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ─── ENDPOINTS OFFICIELS ──────────────────────────────────────────────────────
ENDPOINT_LOGIN        = "/login/"
ENDPOINT_GET_INVOICE  = "/getInvoice/"
ENDPOINT_ADD_INVOICE  = "/addInvoice_confirm/"
ENDPOINT_CHECK_TIN    = "/checkTIN/"
ENDPOINT_CANCEL       = "/cancelInvoice/"
ENDPOINT_STOCK        = "/AddStockMovement/"
ENDPOINT_GET_DMC      = "/getDmcItems/"

TOKEN_CACHE_SECONDS = 50


def get_obr_base_url(societe):
    url = getattr(societe, 'obr_base_url', None)
    if not url or not str(url).strip():
        raise ValueError(
            f"URL Base OBR non configurée pour la société '{societe}'. "
            f"Vérifiez le champ obr_base_url (ex: https://ebms.obr.gov.bi:9443/ebms_api)."
        )
    return str(url).strip().rstrip('/')


def build_obr_url(societe, endpoint):
    return f"{get_obr_base_url(societe)}{endpoint}"


class OBRService:

    @staticmethod
    def _get_token(societe):
        # ... (tout le code de _get_token reste EXACTEMENT le même) ...
        cache_key = f"obr_token_{societe.pk}"
        token = cache.get(cache_key)
        if token:
            return token

        url = build_obr_url(societe, ENDPOINT_LOGIN)

        username = getattr(societe, 'obr_username', None)
        password = getattr(societe, 'obr_password', None)

        if not username or not str(username).strip():
            raise ValueError(f"obr_username non configuré pour '{societe}'.")
        if not password or not str(password).strip():
            raise ValueError(f"obr_password non configuré pour '{societe}'.")

        body = {
            "username": str(username).strip(),
            "password": str(password).strip(),
        }

        response = requests.post(
            url,
            json=body,
            headers={"Content-Type": "application/json"},
            timeout=10,
            verify=False,
        )

        if not response.ok:
            try:
                msg_obr = response.json().get('msg', response.text[:200])
            except Exception:
                msg_obr = response.text[:200]
            raise Exception(f"OBR Login échoué pour '{societe}' [HTTP {response.status_code}] : {msg_obr}")

        result = response.json()
        if not result.get("success"):
            raise Exception(f"OBR Login échoué pour '{societe}' : {result.get('msg')}")

        token = result.get("result", {}).get("token")
        if not token:
            raise Exception(f"OBR Login : token absent. Réponse : {result}")

        cache.set(cache_key, token, timeout=TOKEN_CACHE_SECONDS)
        return token

    @staticmethod
    def _get_taux_tva(societe):
        """
        CORRECTION : Support des taux 0%, 10%, 18% et autres
        """
        qs = TauxTVA.objects.for_societe(societe)

        if getattr(societe, 'assujeti_tva', False):
            # Pour les assujettis : on prend le taux par défaut, sinon le plus élevé
            taux = qs.filter(est_defaut=True).first()
            if not taux:
                taux = qs.order_by('-valeur').first()   # 18% ou 10% selon configuration
        else:
            # Non assujetti → toujours 0%
            taux = qs.filter(valeur=Decimal('0.00')).first()

        return taux or qs.first()

    @staticmethod
    def get_dmc_info(societe, reference_dmc):
        token = OBRService._get_token(societe)
        url   = build_obr_url(societe, ENDPOINT_GET_DMC)

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
        }
        payload = {
            "nif":           str(societe.nif).strip(),
            "reference_dmc": reference_dmc.strip(),
        }

        response = requests.post(
            url, json=payload, headers=headers, timeout=15, verify=False
        )

        if not response.ok:
            try:
                msg_obr = response.json().get('msg', response.text[:200])
            except Exception:
                msg_obr = response.text[:200]
            raise Exception(f"OBR getDmcItems [HTTP {response.status_code}] : {msg_obr}")

        data = response.json()
        if not data.get("success"):
            raise Exception(data.get("msg") or "Aucune donnée trouvée pour ce DMC")

        result = data.get("result", {})
        items  = result.get("items", [])
        if not items:
            raise Exception("La référence DMC n'appartient pas à ce NIF")

        item     = items[0]
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

    # Les autres méthodes (check_tin, diagnostiquer_connexion_obr) restent inchangées
    # ... (code identique) ...
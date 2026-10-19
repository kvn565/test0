import logging
import requests
from django.core.cache import cache
from django.utils import timezone
from django.db import transaction

from facturer.models import Facture, FacturePendingOBR
from facturer.obr_service import envoyer_facture_obr, get_obr_base_url, ENDPOINT_LOGIN
from stock.models import EntreeStock, SortieStock
from stock.obr_service import envoyer_entree_stock, envoyer_sortie_stock

logger = logging.getLogger(__name__)

CACHE_KEY_LAST_RETRY_CHECK = "obr_last_retry_check"
CACHE_KEY_INTERNET_STATUS = "obr_internet_status"
RETRY_CHECK_INTERVAL = 30   # 30 secondes
INTERNET_CHECK_TIMEOUT = 3  # timeout plus court
INTERNET_CHECK_URL = "https://ebms.obr.gov.bi:8443/ebms_api/login/"
INTERNET_CACHE_DURATION = 30  # cache internet 30 sec
CACHE_KEY_SYNC = "obr_last_sync_check"
SYNC_INTERVAL = 60            # synchronisation toutes les 60s si en ligne


def check_internet_connectivity(check_url=None):
    """Vérifie si internet est accessible via l'endpoint OBR réellement utilisé.

    ✅ On utilise l'URL configurée de la société (test :9443 / prod :8443 / URL
    personnalisée) plutôt qu'une URL en dur, sinon la reprise auto pouvait ne
    jamais se déclencher (faux négatif) si l'URL par défaut était injoignable
    alors que l'OBR réel ne l'était pas.
    """
    url = check_url or INTERNET_CHECK_URL
    cache_key = f"{CACHE_KEY_INTERNET_STATUS}:{url}"
    cached_status = cache.get(cache_key)
    if cached_status is not None:
        return cached_status

    try:
        response = requests.get(url, timeout=INTERNET_CHECK_TIMEOUT, verify=False)
        # Si on reçoit une réponse (même 401/404), internet est OK
        is_online = response.status_code < 500
    except Exception:
        is_online = False

    cache.set(cache_key, is_online, INTERNET_CACHE_DURATION)
    return is_online


def auto_retry_pending_obr(limit_per_type=50):
    """
    Retente automatiquement l'envoi OBR pour tous les éléments en attente.
    Appelé quand internet revient.
    """
    # Déterminer l'URL OBR réellement utilisée pour la vérification de connectivité,
    # afin que la reprise se déclenche même en mode test / URL personnalisée.
    sample = (
        Facture.objects.filter(statut_obr='EN_ATTENTE').select_related('societe').first()
        or EntreeStock.objects.filter(statut_obr='EN_ATTENTE').select_related('societe').first()
        or SortieStock.objects.filter(statut_obr='EN_ATTENTE').select_related('societe').first()
    )
    check_url = None
    if sample is not None:
        try:
            check_url = f"{get_obr_base_url(sample.societe)}{ENDPOINT_LOGIN}"
        except Exception:
            check_url = None

    if not check_internet_connectivity(check_url):
        logger.info("[AUTO-RETRY] Internet non disponible, skip")
        return {'traites': 0, 'succes': 0, 'echecs': 0, 'reason': 'offline'}

    last_check = cache.get(CACHE_KEY_LAST_RETRY_CHECK)
    now = timezone.now().timestamp()
    if last_check and (now - last_check) < RETRY_CHECK_INTERVAL:
        logger.info("[AUTO-RETRY] Vérification trop récente, skip")
        return {'traites': 0, 'succes': 0, 'echecs': 0, 'reason': 'rate_limited'}

    cache.set(CACHE_KEY_LAST_RETRY_CHECK, now, RETRY_CHECK_INTERVAL * 2)

    total_traites = 0
    total_succes = 0
    total_echecs = 0

    # 1. FACTURES EN ATTENTE (hors refus définitif OBR = pending FAILED)
    factures_en_attente = Facture.objects.filter(
        statut_obr='EN_ATTENTE'
    ).exclude(
        pending_obr__statut='FAILED'
    ).select_related('societe')[:limit_per_type]

    for facture in factures_en_attente:
        total_traites += 1
        try:
            result = envoyer_facture_obr(facture)
            if result.get('success'):
                total_succes += 1
            else:
                total_echecs += 1
        except Exception as e:
            total_echecs += 1
            logger.error(f"[AUTO-RETRY] Facture {facture.numero} exception: {e}")

    # 2. ENTRÉES STOCK EN ATTENTE
    entrees_en_attente = EntreeStock.objects.filter(
        statut_obr='EN_ATTENTE'
    ).exclude(
        message_obr__icontains='Configuration OBR manquante'
    ).exclude(
        message_obr__icontains='System ID OBR non configure'
    ).select_related('societe', 'produit')[:limit_per_type]

    for entree in entrees_en_attente:
        total_traites += 1
        try:
            success, msg = envoyer_entree_stock(entree)
            if success:
                total_succes += 1
            else:
                total_echecs += 1
        except Exception as e:
            total_echecs += 1
            logger.error(f"[AUTO-RETRY] Entrée {entree.pk} exception: {e}")

    # 3. SORTIES STOCK EN ATTENTE
    sorties_en_attente = SortieStock.objects.filter(
        statut_obr='EN_ATTENTE'
    ).exclude(
        message_obr__icontains='Configuration OBR manquante'
    ).exclude(
        message_obr__icontains='System ID OBR non configure'
    ).select_related('societe', 'entree_stock__produit')[:limit_per_type]

    for sortie in sorties_en_attente:
        total_traites += 1
        try:
            success, msg = envoyer_sortie_stock(sortie)
            if success:
                total_succes += 1
            else:
                total_echecs += 1
        except Exception as e:
            total_echecs += 1
            logger.error(f"[AUTO-RETRY] Sortie {sortie.pk} exception: {e}")

    # 4. NETTOYAGE APRÈS 15 TENTATIVES (hors-ligne prolongée)
    pending_retries = FacturePendingOBR.objects.filter(
        statut='PENDING_RETRY', retry_count__gte=15
    ).select_related('facture')[:limit_per_type]

    for pending in pending_retries:
        total_traites += 1
        facture = pending.facture
        # Échec définitif : nettoyer stock et marquer ECHEC
        with transaction.atomic():
            facture.nettoyer_mouvements_stock()
            facture.statut_obr = 'ECHEC'
            facture.message_obr = f"Echec definitif apres {pending.retry_count} tentatives - stock nettoye"
            facture.save(update_fields=['statut_obr', 'message_obr'])
            pending.statut = 'FAILED'
            pending.message = f"Echec definitif apres {pending.retry_count} tentatives - stock nettoye"
            pending.save(update_fields=['statut', 'message'])
            total_echecs += 1

    logger.info(f"[AUTO-RETRY] Terminé: {total_traites} traités, {total_succes} succès, {total_echecs} échecs")
    return {
        'traites': total_traites,
        'succes': total_succes,
        'echecs': total_echecs,
        'reason': 'completed'
    }


class OBRAutoRetryMiddleware:
    """
    Middleware qui vérifie la connectivité internet et retente les éléments OBR en attente
    quand la connexion revient.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Vérifier et retenter seulement pour les utilisateurs authentifiés
        if request.user.is_authenticated and hasattr(request.user, 'societe'):
            auto_retry_pending_obr(limit_per_type=50)

            # Synchronisation locale <-> online (si activee), debounce 60s
            last_sync = cache.get(CACHE_KEY_SYNC)
            now_ts = timezone.now().timestamp()
            if (not last_sync) or (now_ts - last_sync) > SYNC_INTERVAL:
                cache.set(CACHE_KEY_SYNC, now_ts, SYNC_INTERVAL * 2)
                try:
                    from sync.client import run_sync
                    run_sync(request.user.societe)
                except Exception:
                    pass

        response = self.get_response(request)
        return response

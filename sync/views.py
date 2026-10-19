"""API de synchronisation cote ONLINE (serveur).

Endpoints :
  POST /sync/push/  -> upsert des enregistrements recus du local
  GET  /sync/pull/  -> renvoie les enregistrements modifies depuis 'since'

Authentification : en-tete "Authorization: Bearer <token>" (SyncToken).
"""
import json

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import SyncToken
from .registry import SYNC_ORDER, SYNC_REGISTRY
from .serializers import from_record, to_record


def _resolve_societe(request):
    auth = request.META.get('HTTP_AUTHORIZATION', '')
    token = auth[7:].strip() if auth.startswith('Bearer ') else None
    if not token:
        return None
    try:
        return SyncToken.objects.select_related('societe').get(token=token).societe
    except SyncToken.DoesNotExist:
        return None


@csrf_exempt
def sync_push(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST requis'}, status=405)

    societe = _resolve_societe(request)
    if societe is None:
        return JsonResponse({'ok': False, 'error': 'Non autorise'}, status=401)

    try:
        payload = json.loads(request.body or b'{}')
        records = payload.get('records', [])
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)

    applied = 0
    factures_a_envoyer = []

    for rec in records:
        obj = from_record(rec, societe)
        if obj is None:
            # doublon ignore (meme numero deja envoye)
            continue
        obj.save()
        applied += 1
        if obj.__class__.__name__ == 'Facture' and obj.statut_obr == 'EN_ATTENTE':
            if obj.lignes.exists():
                factures_a_envoyer.append(obj)
            else:
                obj.message_obr = (obj.message_obr or '') + ' [sync: lignes manquantes]'
                obj.save(update_fields=['message_obr'])

    # L'online a internet : il envoie a l'OBR les factures EN_ATTENTE recues
    from facturer.obr_service import envoyer_facture_obr
    for f in factures_a_envoyer:
        try:
            if not f.lignes.exists():
                continue
            f.recalculer_totaux()
            envoyer_facture_obr(f)
        except Exception:
            pass

    return JsonResponse({'ok': True, 'applied': applied})


@csrf_exempt
def sync_pull(request):
    societe = _resolve_societe(request)
    if societe is None:
        return JsonResponse({'ok': False, 'error': 'Non autorise'}, status=401)

    from django.utils.dateparse import parse_datetime
    since = request.GET.get('since')
    since_dt = parse_datetime(since) if since else None

    out = []
    for label in SYNC_ORDER:
        model = SYNC_REGISTRY[label]['model']
        qs = model.objects.filter(societe=societe)
        if since_dt:
            qs = qs.filter(sync_updated_at__gt=since_dt)
        for obj in qs:
            out.append(to_record(obj, label))

    return JsonResponse({'ok': True, 'records': out})

"""Client de synchronisation cote LOCAL (celui qui pousse/tire vers l'online)."""
import json
import uuid

import requests
from django.utils import timezone

from .registry import SYNC_ORDER, SYNC_REGISTRY
from .serializers import from_record, to_record
from .models import SyncState


def _ensure_uuid(obj):
    if not obj.sync_uuid:
        obj.sync_uuid = str(uuid.uuid4())
        obj.save()
    return obj


def _state(societe, model_name):
    return SyncState.objects.get_or_create(societe=societe, model_name=model_name)[0]


def run_sync(societe):
    """Pousse les modifs locales et tire les modifs de l'online. Non bloquant."""
    from facturer.obr_auto_retry import check_internet_connectivity

    profile = getattr(societe, 'sync_profile', None)
    if not profile or not profile.enabled or not profile.remote_base_url or not profile.api_token:
        return {'ok': False, 'reason': 'disabled'}

    base = profile.remote_base_url.rstrip('/')
    headers = {'Authorization': 'Bearer ' + profile.api_token, 'Content-Type': 'application/json'}

    if not check_internet_connectivity(base + '/sync/pull/'):
        return {'ok': False, 'reason': 'offline'}

    try:
        # ---- PUSH (local -> online) ----
        push_payload = []
        for label in SYNC_ORDER:
            model = SYNC_REGISTRY[label]['model']
            st = _state(societe, label)
            qs = model.objects.filter(societe=societe)
            if st.last_push_at:
                qs = qs.filter(sync_updated_at__gt=st.last_push_at)
            for obj in qs:
                _ensure_uuid(obj)
                push_payload.append(to_record(obj, label))

        r = requests.post(base + '/sync/push/', headers=headers,
                          data=json.dumps({'records': push_payload}), timeout=60, verify=False)
        if r.status_code != 200:
            raise Exception('push HTTP %s' % r.status_code)
        for label in SYNC_ORDER:
            s = _state(societe, label)
            s.last_push_at = timezone.now()
            s.save()

        # ---- PULL (online -> local) ----
        states = {label: _state(societe, label) for label in SYNC_ORDER}
        dates = [states[l].last_pull_at for l in SYNC_ORDER if states[l].last_pull_at]
        since = max(dates) if dates else None
        params = {'since': since.isoformat() if since else ''}

        r2 = requests.get(base + '/sync/pull/', headers=headers, params=params, timeout=60, verify=False)
        if r2.status_code != 200:
            raise Exception('pull HTTP %s' % r2.status_code)
        data = r2.json()
        for rec in data.get('records', []):
            obj = from_record(rec, societe)
            if obj is None:
                continue
            obj.save()
            if obj.__class__.__name__ == 'Facture':
                try:
                    obj.recalculer_totaux()
                except Exception:
                    pass
        for label in SYNC_ORDER:
            s = states[label]
            s.last_pull_at = timezone.now()
            s.save()

        profile.last_error = ''
        profile.save()
        return {'ok': True, 'pushed': len(push_payload)}

    except Exception as e:
        profile.last_error = str(e)[:500]
        profile.save()
        return {'ok': False, 'error': str(e)}

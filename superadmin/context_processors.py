from datetime import datetime, timedelta

from django.utils import timezone


def licence_notification(request):
    """Ajoute licence_15j au contexte pour la notification de licence expirante."""
    result = {'licence_15j': False}

    if not request.user.is_authenticated or request.user.is_superuser:
        return result

    societe = getattr(request.user, 'societe', None)
    if not societe:
        return result

    cle = societe.cle_active
    if not cle:
        return result

    jours = cle.jours_restants
    if not (1 <= jours <= 15):
        return result

    dismissed = request.session.get('licence_notif_dismissed')
    if not dismissed:
        result['licence_15j'] = jours
    else:
        try:
            dt = datetime.fromisoformat(dismissed)
            if dt.tzinfo is None:
                dt = timezone.make_aware(dt)
            if (timezone.now() - dt) > timedelta(hours=24):
                result['licence_15j'] = jours
        except (ValueError, TypeError):
            result['licence_15j'] = jours

    return result


def obr_mode(request):
    """Ajoute obr_live (bool) et obr_label (LIVE/TEST) au contexte."""
    result = {'obr_live': False, 'obr_label': 'TEST'}
    if not request.user.is_authenticated:
        return result
    societe = getattr(request.user, 'societe', None)
    if not societe:
        return result
    live = bool(societe.obr_mode_production)
    return {'obr_live': live, 'obr_label': 'LIVE' if live else 'TEST'}

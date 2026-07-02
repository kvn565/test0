from .models import AppConfig

def app_config(request):
    config = AppConfig.objects.first()
    if not config:
        config = AppConfig.objects.create(app_name='WIBABI')
    return {'app_config': config}


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

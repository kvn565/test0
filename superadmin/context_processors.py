from .models import AppConfig

def app_config(request):
    config = AppConfig.objects.first()
    if not config:
        config = AppConfig.objects.create(app_name='WIBABI')
    return {'app_config': config}

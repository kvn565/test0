from django.urls import path

from .views import sync_push, sync_pull

app_name = 'sync'

urlpatterns = [
    path('push/', sync_push, name='sync_push'),
    path('pull/', sync_pull, name='sync_pull'),
]

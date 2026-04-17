# clients/urls.py

from django.urls import path
from . import views

app_name = 'clients'

urlpatterns = [
    # ── Clients ──────────────────────────────────────────────────
    path('',                           views.liste_clients,    name='liste'),
    path('creer/',                     views.creer_client,     name='creer'),
    path('<int:pk>/modifier/',         views.edit_client,      name='modifier'),
    path('<int:pk>/supprimer/',        views.delete_client,    name='supprimer'),

    # ── Types de client ──────────────────────────────────────────
    path('types/',                     views.types_clients,     name='types'),
    path('types/creer/',               views.creer_type_client, name='creer_type'),
    path('types/<int:pk>/modifier/',   views.edit_type_client,  name='modifier_type'),
    path('types/<int:pk>/supprimer/',  views.delete_type_client,name='supprimer_type'),
]

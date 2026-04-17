from django.urls import path
from . import views   # ← ça importe déjà tout le module views

app_name = 'clients'

urlpatterns = [
    # ── Clients ──────────────────────────────────────────────────
    path('',                           views.liste_clients,    name='liste'),
    path('creer/',                     views.creer_client,     name='creer'),
    path('<int:pk>/modifier/',         views.edit_client,      name='modifier'),
    path('<int:pk>/supprimer/',        views.delete_client,    name='supprimer'),
    
    # ← Ajoute l'import ici : utilise views. + nom de la vue
    path('ajax/verifier-nif/',         views.ajax_verifier_nif, name='verifier_nif'),

    # ── Types de client ──────────────────────────────────────────
    path('types/',                     views.types_clients,     name='types'),
    path('types/creer/',               views.creer_type_client, name='creer_type'),
    path('types/<int:pk>/modifier/',   views.edit_type_client,  name='modifier_type'),
    path('types/<int:pk>/supprimer/',  views.delete_type_client,name='supprimer_type'),
]
# produits/urls.py
from django.urls import path
from . import views

app_name = 'produits'

urlpatterns = [
    # ─── Liste & recherche ───────────────────────────────────────────────────────
    path('', views.produit_liste, name='liste'),

    # ─── Création ────────────────────────────────────────────────────────────────
    path('creer/local/',   views.produit_creer_local,   name='creer_local'),
    path('creer/importe/', views.produit_creer_importe, name='creer_importe'),

    # ─── Modification & suppression ──────────────────────────────────────────────
    path('<int:pk>/modifier/',  views.produit_modifier,   name='modifier'),
    path('<int:pk>/supprimer/', views.produit_supprimer,  name='supprimer'),

    # ─── Actions AJAX ────────────────────────────────────────────────────────────
    path('ajax/importer-dmc/', views.ajax_importer_dmc, name='ajax_importer_dmc'),
]
# stock/urls.py
from django.urls import path
from . import views

app_name = 'stock'

urlpatterns = [
    # Entrées
    path('entrees/',                              views.entree_liste,          name='entrees'),
    path('entrees/nouveau/',                      views.entree_creer,          name='entree_nouveau'),
    path('entrees/<int:pk>/',                     views.entree_detail,         name='entree_detail'),
    path('entrees/<int:pk>/modifier/',            views.entree_modifier,       name='entree_modifier'),
    path('entrees/<int:pk>/supprimer/',           views.entree_supprimer,      name='entree_supprimer'),
    path('entrees/<int:pk>/reenvoyer-obr/',       views.entree_reenvoyer_obr,  name='entree_reenvoyer_obr'),
    # Entrées
    path('entrees/refresh-obr/', views.refresh_obr, name='refresh_obr'),
    # Réenvoi OBR via AJAX
    path('entrees/<int:pk>/refresh-obr/', views.refresh_obr, name='refresh_obr'),

    # Sorties
    path('sorties/',                              views.sortie_liste,          name='sorties'),
    path('sorties/nouveau/',                      views.sortie_creer,          name='sortie_nouveau'),
    path('sorties/<int:pk>/',                     views.sortie_detail,         name='sortie_detail'),
    path('sorties/<int:pk>/modifier/',            views.sortie_modifier,       name='sortie_modifier'),
    path('sorties/<int:pk>/supprimer/',           views.sortie_supprimer,      name='sortie_supprimer'),
    path('sorties/<int:pk>/reenvoyer-obr/',       views.sortie_reenvoyer_obr,  name='sortie_reenvoyer_obr'),

    # AJAX
    path('api/stock-disponible/',                 views.stock_disponible,      name='stock_disponible'),
]

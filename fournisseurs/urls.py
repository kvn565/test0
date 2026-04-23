# fournisseurs/urls.py
from django.urls import path
from . import views

app_name = 'fournisseurs'

urlpatterns = [
    path('',                    views.fournisseur_liste,     name='liste'),
    path('nouveau/',            views.fournisseur_creer,     name='nouveau'),
    path('<int:pk>/modifier/',  views.fournisseur_modifier,  name='modifier'),
    path('<int:pk>/supprimer/', views.fournisseur_supprimer, name='supprimer'),
]

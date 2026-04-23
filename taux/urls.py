# taux/urls.py
from django.urls import path
from . import views

app_name = 'taux'

urlpatterns = [
    path('',                    views.taux_liste,     name='liste'),
    path('nouveau/',            views.taux_creer,     name='nouveau'),
    path('<int:pk>/modifier/',  views.taux_modifier,  name='modifier'),
    path('<int:pk>/supprimer/', views.taux_supprimer, name='supprimer'),
]

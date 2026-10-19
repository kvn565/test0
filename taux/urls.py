# taux/urls.py
from django.urls import path
from . import views

app_name = 'taux'

urlpatterns = [
    path('',                    views.taux_liste,     name='liste'),
    path('nouveau/',            views.taux_creer,     name='nouveau'),
    path('nouveau/<str:type_taux>/', views.taux_creer, name='nouveau_type'),
    path('<int:pk>/modifier/',  views.taux_modifier,  name='modifier'),
    path('<str:type_taux>/<int:pk>/modifier/', views.taux_modifier, name='modifier_type'),
    path('<int:pk>/supprimer/', views.taux_supprimer, name='supprimer'),
    path('<str:type_taux>/<int:pk>/supprimer/', views.taux_supprimer, name='supprimer_type'),
]
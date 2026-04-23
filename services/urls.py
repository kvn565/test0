# services/urls.py
from django.urls import path
from . import views

app_name = 'services'

urlpatterns = [
    path('',                    views.service_liste,     name='liste'),
    path('nouveau/',            views.service_creer,     name='nouveau'),
    path('<int:pk>/modifier/',  views.service_modifier,  name='modifier'),
    path('<int:pk>/supprimer/', views.service_supprimer, name='supprimer'),
]

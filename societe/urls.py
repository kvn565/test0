# societe/urls.py
from django.urls import path
from . import views

app_name = 'societe'

urlpatterns = [
    path('',               views.societe_liste, name='liste'),
    path('ajax/modifier/', views.ajax_modifier, name='ajax_modifier'),
]

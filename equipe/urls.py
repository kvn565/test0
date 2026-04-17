# equipe/urls.py
from django.urls import path
from . import views

app_name = 'equipe'

urlpatterns = [
    # Page principale
    path('',                              views.liste_equipe,           name='liste'),

    # AJAX
    path('creer/',                        views.ajax_creer_employe,     name='creer'),
    path('<int:pk>/modifier/',            views.ajax_modifier_employe,  name='modifier'),
    path('<int:pk>/supprimer/',           views.ajax_supprimer_employe, name='supprimer'),
    path('<int:pk>/mdp/',                 views.ajax_changer_mdp_employe, name='mdp'),
    path('<int:pk>/info/',                views.ajax_info_employe,      name='info'),
]

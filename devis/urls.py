from django.urls import path
from . import views

app_name = 'devis'

urlpatterns = [
    path('',                          views.devis_liste,                       name='liste'),
    path('<int:pk>/',                 views.devis_detail,                      name='detail'),
    path('<int:pk>/supprimer/',       views.devis_supprimer,                   name='supprimer'),
    path('<int:pk>/valider/',         views.devis_valider,                     name='valider'),
    path('<int:pk>/transformer/',     views.devis_transformer_en_facture,      name='transformer'),
    path('<int:pk>/imprimer/',        views.devis_imprimer,                    name='imprimer'),
    path('<int:pk>/envoyer-email/',   views.devis_envoyer_email,               name='envoyer_email'),
    path('ajax/creer/',               views.ajax_creer_devis,                  name='ajax-creer'),
    path('ajax/ajouter-ligne/',       views.ajax_ajouter_ligne_devis,          name='ajax-ajouter-ligne'),
    path('ajax/supprimer-ligne/',     views.ajax_supprimer_ligne_devis,        name='ajax-supprimer-ligne'),
    path('ajax/modifier-ligne/',      views.ajax_modifier_ligne_devis,         name='ajax-modifier-ligne'),
    path('ajax/info-produit/<int:pk>/', views.ajax_info_produit_devis,         name='ajax-info-produit'),
    path('ajax/info-service/<int:pk>/', views.ajax_info_service_devis,         name='ajax-info-service'),
    path('public/<str:uuid>/',        views.devis_public,                      name='public'),
]

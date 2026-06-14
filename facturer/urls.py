# facturer/urls.py
from django.urls import path
from . import views
from . import devis_views

app_name = 'facturer'

urlpatterns = [
    # ─── Pages principales ─────────────────────────────────────────────────────
    path('',                              views.facture_liste,          name='liste'),
    path('<int:pk>/',                     views.facture_detail,         name='detail'),

    # ─── Devis ─────────────────────────────────────────────────────────────────
    path('devis/',                         devis_views.devis_liste,                name='devis_liste'),
    path('devis/<int:pk>/',                devis_views.devis_detail,               name='devis_detail'),
    path('devis/<int:pk>/supprimer/',      devis_views.devis_supprimer,            name='devis_supprimer'),
    path('devis/<int:pk>/valider/',        devis_views.devis_valider,              name='devis_valider'),
    path('devis/<int:pk>/transformer/',    devis_views.devis_transformer_en_facture, name='devis_transformer'),
    path('devis/<int:pk>/imprimer/',       devis_views.devis_imprimer,             name='devis_imprimer'),

    path('devis/ajax/creer/',              devis_views.ajax_creer_devis,           name='devis-ajax-creer'),
    path('devis/ajax/ajouter-ligne/',      devis_views.ajax_ajouter_ligne_devis,   name='devis-ajax-ajouter-ligne'),
    path('devis/ajax/supprimer-ligne/',    devis_views.ajax_supprimer_ligne_devis, name='devis-ajax-supprimer-ligne'),
    path('devis/ajax/modifier-ligne/',     devis_views.ajax_modifier_ligne_devis,  name='devis-ajax-modifier-ligne'),
    path('devis/ajax/info-produit/<int:pk>/', devis_views.ajax_info_produit_devis, name='devis-ajax-info-produit'),
    path('devis/ajax/info-service/<int:pk>/', devis_views.ajax_info_service_devis, name='devis-ajax-info-service'),

    # ─── Annulation de facture ────────────────────────────────────────────────
    path('<int:pk>/annuler/',             views.facture_annuler,        name='annuler'),

    # ─── Impression et PDF ─────────────────────────────────────────────────────
    path('<int:pk>/imprimer/a4/',         views.facture_imprimer_a4,    name='imprimer-a4'),
    path('<int:pk>/imprimer/pos/',        views.facture_imprimer_pos,   name='imprimer-pos'),
    path('<int:pk>/pdf/',                 views.facture_generer_pdf,    name='generer_pdf'),
    path('<int:pk>/pos-pdf/',             views.facture_generer_pos_pdf, name='generer_pos_pdf'),

    # ─── AJAX — Gestion des lignes (avec trailing slash obligatoire) ───────────
    path('ajax/creer/',                   views.ajax_creer_facture,     name='ajax-creer-facture'),
    path('ajax/ajouter-ligne/',           views.ajax_ajouter_ligne,     name='ajax-ajouter-ligne'),
    path('ajax/modifier-ligne/',          views.ajax_modifier_ligne,    name='ajax-modifier-ligne'),
    path('ajax/supprimer-ligne/',         views.ajax_supprimer_ligne,   name='ajax-supprimer-ligne'),

    # ─── AJAX — Informations produit/service ───────────────────────────────────
    path('ajax/info-produit/<int:pk>/',   views.ajax_info_produit,      name='ajax-info-produit'),
    path('ajax/info-service/<int:pk>/',   views.ajax_info_service,      name='ajax-info-service'),

    # ─── AJAX — Pour les avoirs ────────────────────────────────────────────────
    path('ajax/factures-client/<int:client_id>/', 
         views.ajax_get_factures_client, 
         name='ajax_get_factures_client'),

    path('ajax/produits-facture/<int:facture_id>/', 
         views.ajax_get_produits_facture_originale, 
         name='ajax_get_produits_facture_originale'),

    # ─── Intégration OBR ───────────────────────────────────────────────────────
    path('ajax/envoyer-obr/<int:pk>/',    views.ajax_envoyer_obr,       name='ajax-envoyer-obr'),

     path('ajax/supprimer-facture-en-attente/', 
         views.ajax_supprimer_facture_en_attente, 
         name='ajax-supprimer-facture-en-attente'),   # ← Nom avec tirets
]
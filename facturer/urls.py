# facturer/urls.py
from django.urls import path
from . import views

app_name = 'facturer'

urlpatterns = [
    # ─── Pages principales ─────────────────────────────────────────────────────
    path('',                              views.facture_liste,          name='liste'),
    path('<int:pk>/',                     views.facture_detail,         name='detail'),

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
     name='ajax_supprimer_facture_en_attente'),
]
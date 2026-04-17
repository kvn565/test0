# superadmin/urls.py — VERSION FINALE
# LOGIQUE : superadmin enregistre société → clé essai 14j auto → chef s'inscrit via NIF

from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

app_name = 'superadmin'

urlpatterns = [

    # ── Dashboard ─────────────────────────────────────────────────
    path('', views.dashboard, name='dashboard'),

    # ── Setup & licence ───────────────────────────────────────────
    # ⚠️  /setup/ est défini dans facturation/urls.py (URLs racine) — PAS ici.
    #    Raison : RateLimitMiddleware protège /setup/ par chemin exact.
    #    Si /setup/ est ici → URL = /superadmin/setup/ → middleware ne le reconnaît PAS.
    path('saisir-cle/',        views.saisir_cle_payante,  name='saisir_cle'),
    path('licence-expiree/',   views.licence_expiree,     name='licence_expiree'),

    # ── Sociétés ──────────────────────────────────────────────────
    path('societes/',                           views.societes_liste,    name='societes_liste'),
    path('societes/creer/',                     views.societe_creer,     name='societe_creer'),
    path('societes/<int:pk>/',                  views.societe_detail,    name='societe_detail'),
    path('societes/<int:pk>/modifier/',         views.societe_modifier,  name='societe_modifier'),
    path('societes/<int:pk>/toggle/',           views.societe_toggle,    name='societe_toggle'),
    path('societes/<int:pk>/supprimer/',        views.societe_supprimer, name='societe_supprimer'),
    path('societes/<int:pk>/cle/',              views.cle_generer,       name='cle_generer'),
    path('societes/<int:pk>/ajax-cles/',        views.ajax_cles_societe, name='ajax_cles_societe'),

    # ── Clés d'activation ─────────────────────────────────────────
    path('cles/',                               views.liste_cles,            name='liste_cles'),
    path('cles/creer/',                         views.creer_cle_activation,  name='creer_cle'),
    path('cles/<int:pk>/',                      views.cle_detail,            name='cle_detail'),
    path('cles/<int:pk>/revoquer/',             views.cle_revoquer,          name='cle_revoquer'),

    # ── Utilisateurs ──────────────────────────────────────────────
    path('utilisateurs/',                       views.utilisateurs_liste,         name='utilisateurs'),
    path('utilisateurs/creer/',                 views.ajax_creer_utilisateur,     name='user_creer'),
    path('utilisateurs/<int:pk>/modifier/',     views.ajax_modifier_utilisateur,  name='user_modifier'),
    path('utilisateurs/<int:pk>/supprimer/',    views.ajax_supprimer_utilisateur, name='user_supprimer'),
    path('utilisateurs/<int:pk>/mdp/',          views.ajax_changer_mot_de_passe,  name='user_mdp'),
    path('utilisateurs/<int:pk>/info/',         views.ajax_info_utilisateur,      name='user_info'),
    path('societes/gestion/', views.societe_gestion_liste, name='societe_gestion_liste'),
    path('societes/gestion/<int:pk>/edit/', views.societe_gestion_modifier, name='societe_gestion_modifier'),
    path('login/', auth_views.LoginView.as_view(template_name='superadmin/login.html'), name='login'),

    # ── Backup ────────────────────────────────────────────────────
    path('backup/',                             views.backup_page,        name='backup'),
    path('backup/creer/',                       views.backup_creer,       name='backup_creer'),
    path('backup/<int:pk>/telecharger/',        views.backup_telecharger, name='backup_telecharger'),

    # ── Réinitialisation ──────────────────────────────────────────
    path('reinitialisation/',                   views.reinitialisation_page,      name='reinitialisation'),
    path('reinitialisation/confirmer/',         views.reinitialisation_confirmer, name='reinitialisation_confirmer'),
]

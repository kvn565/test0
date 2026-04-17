# accounts/urls.py

from django.urls import path
from . import views

app_name = 'accounts'   # ✅ CORRIGÉ : était 'account' → base.html utilise 'accounts:'

urlpatterns = [
    # ── Authentification ──────────────────────────────────────────
    path('login/',    views.login_view,   name='login'),
    path('logout/',   views.logout_view,  name='logout'),

    # ── Profil ────────────────────────────────────────────────────
    # ✅ AJOUTÉ : base.html référence {% url 'accounts:profil' %}
    path('profil/',   views.profil_view,  name='profil'),

    # ── DÉPLACÉ : accueil/ est dans le urls.py principal du projet ──────
    # name='accueil' doit être global (utilisé par redirect('accueil'))
    # path('accueil/', ...) → facturation/urls.py → name='accueil'

    # ── Pages d'état société ──────────────────────────────────────
    # Affichées quand le compte est bloqué pour une raison métier
    path('attente/',  views.attente_view,  name='attente'),   # Aucune clé attribuée
    path('inactif/',  views.inactif_view,  name='inactif'),   # Société inactive
    path('suspendu/', views.suspendu_view, name='suspendu'),  # Clé révoquée

    # ── SUPPRIMÉ : setup/ ─────────────────────────────────────────
    # L'inscription du chef est maintenant gérée par superadmin:inscription_chef
    # URL : /setup/ → définie dans le urls.py principal → superadmin/views.py

    # ── SUPPRIMÉ : activer/ ───────────────────────────────────────
    # La réactivation est gérée par :
    #   1. Le modal AJAX dans base.html (via superadmin:saisir_cle)
    #   2. Le middleware LicenceMiddleware → redirect vers /licence-expiree/
    #   3. La page superadmin/licence_expiree.html
]

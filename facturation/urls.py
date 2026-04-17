# facturation/urls.py

from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static

# Imports directs pour les URLs hors namespace
from accounts.views import accueil_view
from superadmin.views import inscription_chef

# ═══════════════════════════════════════════════════════════════
#  NOTES IMPORTANTES
#  ─────────────────────────────────────────────────────────────
#
#  ✅ /setup/ EST ICI (pas dans superadmin/urls.py) car :
#    1. RateLimitMiddleware protège '/setup/' → doit être à la racine
#    2. LicenceMiddleware exempte '/setup/'   → doit être à la racine
#    → name='inscription_chef' → {% url 'inscription_chef' %} dans login.html
#
#  ✅ /accueil/ EST ICI (pas dans accounts/urls.py) car :
#    → redirect('accueil') dans les vues cherche un nom GLOBAL
#    → doit être dans le urlconf racine, pas dans un sous-namespace
#
# ═══════════════════════════════════════════════════════════════

urlpatterns = [

    # ── Admin Django ──────────────────────────────────────────────
    path('admin/', admin.site.urls),

    # ── Setup initial ─────────────────────────────────────────────
    # Hors namespace pour que le rate limiting et l'exemption fonctionnent
    # Accessible SANS licence (exempté dans LicenceMiddleware.EXEMPT_PATHS)
    # Rate-limité par RateLimitMiddleware (max 5 POST sur /setup/ en 5 min)
    path('setup/', inscription_chef, name='inscription_chef'),
    path('equipe/', include('equipe.urls')),

    # ── Authentification ──────────────────────────────────────────
    path('accounts/', include('accounts.urls', namespace='accounts')),

    # ── Superadmin ────────────────────────────────────────────────
    # Inclut : dashboard, sociétés, licences, clés, utilisateurs,
    #          /superadmin/saisir-cle/, /superadmin/licence-expiree/,
    #          /superadmin/backup/, /superadmin/reinitialisation/
    path('superadmin/', include('superadmin.urls', namespace='superadmin')),

    # ── Fiche société (vue chef) ──────────────────────────────────
    path('societe/', include('societe.urls', namespace='societe')),

    # ── Modules stock ─────────────────────────────────────────────
    path('categories/', include('categories.urls', namespace='categories')),

    # ⚠️  À décommenter au fur et à mesure de la création des modules :
    path('taux/',         include('taux.urls',         namespace='taux')),
    path('fournisseurs/', include('fournisseurs.urls', namespace='fournisseurs')),
    path('produits/',     include('produits.urls',     namespace='produits')),
    path('services/',     include('services.urls',     namespace='services')),
    path('stock/',        include('stock.urls',        namespace='stock')),

    # ── Module facturation ────────────────────────────────────────
    path('clients/', include('clients.urls', namespace='clients')),

    # ⚠️  À décommenter au fur et à mesure de la création des modules :
    path('facturer/',     include('facturer.urls',     namespace='facturer')),
    path('rapports/',     include('rapports.urls',     namespace='rapports')),

    # ── Accueil principal (nom global requis) ─────────────────────
    # name='accueil' → utilisé par redirect('accueil') dans accounts/views.py
    # La vue a @login_required, puis LicenceMiddleware vérifie la licence
    path('accueil/', accueil_view, name='accueil'),

    # ── Racine → login ────────────────────────────────────────────
    path('', lambda req: redirect('accounts:login')),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

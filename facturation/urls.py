from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# ====================== IMPORTS DES VUES ======================
from accounts.views import accueil_view, landing_view        # ← Landing page
from superadmin.views import inscription_chef                 # ← Important !

urlpatterns = [
    # Admin Django
    path('admin/', admin.site.urls),

    # Setup initial (création du premier chef)
    path('setup/', inscription_chef, name='inscription_chef'),

    # Autres applications
    path('equipe/', include('equipe.urls')),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('superadmin/', include('superadmin.urls', namespace='superadmin')),
    path('societe/', include('societe.urls', namespace='societe')),
    path('categories/', include('categories.urls', namespace='categories')),
    path('taux/', include('taux.urls', namespace='taux')),
    path('fournisseurs/', include('fournisseurs.urls', namespace='fournisseurs')),
    path('produits/', include('produits.urls', namespace='produits')),
    path('services/', include('services.urls', namespace='services')),
    path('stock/', include('stock.urls', namespace='stock')),
    path('clients/', include('clients.urls', namespace='clients')),
    path('devis/', include('devis.urls', namespace='devis')),
    path('facturer/', include('facturer.urls', namespace='facturer')),
    path('rapports/', include('rapports.urls', namespace='rapports')),

    # Landing Page (page d'accueil publique)
    path('', landing_view, name='index'),

    # Page après connexion
    path('accueil/', accueil_view, name='accueil'),
]

# Fichiers médias en développement
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
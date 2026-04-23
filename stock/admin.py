# stock/admin.py
from django.contrib import admin
from .models import EntreeStock, SortieStock


@admin.register(EntreeStock)
class EntreeStockAdmin(admin.ModelAdmin):
    list_display  = ['societe', 'type_entree', 'produit', 'quantite', 'prix_revient', 'prix_vente_actuel', 'statut_obr', 'date_entree']
    list_filter   = ['societe', 'type_entree', 'statut_obr']
    search_fields = ['produit__designation', 'numero_ref', 'fournisseur__nom']
    date_hierarchy = 'date_entree'


@admin.register(SortieStock)
class SortieStockAdmin(admin.ModelAdmin):
    list_display  = ['societe', 'type_sortie', 'entree_stock', 'quantite', 'prix', 'statut_obr', 'date_sortie']
    list_filter   = ['societe', 'type_sortie', 'statut_obr']
    search_fields = ['entree_stock__produit__designation', 'code']
    date_hierarchy = 'date_sortie'

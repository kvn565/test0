# produits/admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import Produit


@admin.register(Produit)
class ProduitAdmin(admin.ModelAdmin):
    list_display  = ['code', 'designation', 'societe', 'categorie', 'origine', 'prix_vente', 'devise', 'statut', 'obr_import_badge']
    list_filter   = ['societe', 'origine', 'statut', 'categorie']
    search_fields = ['code', 'designation']

    fieldsets = (
        ('Informations générales', {
            'fields': ('societe', 'categorie', 'code', 'designation', 'unite', 'prix_vente', 'devise', 'taux_tva', 'statut', 'origine'),
        }),
        ('📦 Informations OBR — Importation', {
            'fields': ('reference_dmc', 'rubrique_tarifaire', 'nombre_par_paquet', 'description_paquet'),
            'description': 'Ces champs sont obligatoires pour les produits importés avant tout enregistrement de stock.',
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='OBR Import')
    def obr_import_badge(self, obj):
        if obj.origine != 'IMPORTE':
            return format_html('<span style="color:gray;">—</span>')
        if obj.infos_import_completes:
            return format_html('<span style="color:green;">✅ Complet</span>')
        return format_html('<span style="color:red;">⚠️ Incomplet</span>')

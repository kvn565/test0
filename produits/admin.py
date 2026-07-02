# produits/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import Produit


@admin.register(Produit)
class ProduitAdmin(admin.ModelAdmin):
    list_display = [
        'code',
        'designation',
        'societe',
        'categorie',
        'origine',
        'prix_vente',
        'devise',
        'statut',
        'obr_import_badge'
    ]
    
    list_filter   = ['societe', 'origine', 'statut', 'categorie']
    search_fields = ['code', 'designation']

    fieldsets = (
        ('Informations générales', {
            'fields': (
                'societe', 'categorie', 'code', 'designation', 'unite',
                'prix_vente', 'devise', 'taux_tva', 'statut', 'origine'
            ),
        }),
        ('📦 Informations OBR — Importation', {
            'fields': (
                'reference_dmc', 
                'rubrique_tarifaire', 
                'nombre_par_paquet', 
                'description_paquet'
            ),
            'description': 'Ces champs sont obligatoires pour les produits importés avant tout enregistrement de stock.',
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='OBR Import')
    def obr_import_badge(self, obj):
        """Badge OBR dans la liste admin"""
        if getattr(obj, 'origine', None) != 'IMPORTE':
            return mark_safe('<span style="color:#888;">—</span>')
        
        if getattr(obj, 'infos_obr_completes', False):
            return mark_safe(
                '<span style="color:green; font-weight:bold;">✅ Complet</span>'
            )
        else:
            return mark_safe(
                '<span style="color:#d9534f; font-weight:bold;">⚠️ Incomplet</span>'
            )
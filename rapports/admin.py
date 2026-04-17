# rapports/admin.py
from django.contrib import admin
from .models import Rapport


@admin.register(Rapport)
class RapportAdmin(admin.ModelAdmin):
    list_display  = ['type_rapport', 'societe', 'date_debut', 'date_fin', 'cree_par', 'date_creation']
    list_filter   = ['societe', 'type_rapport', 'date_creation']
    search_fields = ['type_rapport']

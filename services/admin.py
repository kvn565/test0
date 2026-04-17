# services/admin.py
from django.contrib import admin
from .models import Service


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display  = ['designation', 'societe', 'prix_vente', 'taux_tva', 'statut', 'date_creation']
    list_filter   = ['societe', 'statut']
    search_fields = ['designation']

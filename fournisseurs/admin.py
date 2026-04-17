# fournisseurs/admin.py
from django.contrib import admin
from .models import Fournisseur


@admin.register(Fournisseur)
class FournisseurAdmin(admin.ModelAdmin):
    list_display  = ['nom', 'societe', 'telephone', 'adresse', 'date_creation']
    list_filter   = ['societe']
    search_fields = ['nom', 'telephone']

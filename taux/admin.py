# taux/admin.py
from django.contrib import admin
from .models import Taux


@admin.register(Taux)
class TauxAdmin(admin.ModelAdmin):
    list_display  = ['nom', 'valeur', 'societe', 'date_creation']
    list_filter   = ['societe']
    search_fields = ['nom']

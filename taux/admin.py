from django.contrib import admin
from .models import TauxTVA


@admin.register(TauxTVA)
class TauxTVAAdmin(admin.ModelAdmin):
    list_display = ('valeur_display', 'societe', 'est_defaut', 'date_creation')
    list_filter = ('societe', 'est_defaut')
    search_fields = ('valeur', 'societe__nom')
    ordering = ('societe__nom', 'valeur')

    # ====================== CORRECTION ======================
    readonly_fields = ('date_creation',)   # ← On enlève date_modification

    # Protection suppression
    def has_delete_permission(self, request, obj=None):
        if obj is None:
            return True

        # Empêche la suppression si le taux est utilisé
        if obj.produits.exists() or (hasattr(obj, 'services') and obj.services.exists()):
            return False

        return super().has_delete_permission(request, obj)

    def valeur_display(self, obj):
        return f"{obj.valeur} %"
    valeur_display.short_description = "Taux TVA"
    valeur_display.admin_order_field = 'valeur'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('societe')
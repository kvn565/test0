# stock/admin.py
from django.contrib import admin, messages
from django.urls import path, reverse
from django.utils.html import format_html
from django.shortcuts import redirect, get_object_or_404
from django.db import transaction
from decimal import Decimal
from django.utils import timezone

from .models import EntreeStock, SortieStock
from .obr_service import envoyer_entree_stock
import logging

logger = logging.getLogger(__name__)


@admin.register(EntreeStock)
class EntreeStockAdmin(admin.ModelAdmin):
    list_display  = ['societe', 'type_entree', 'produit', 'quantite', 'prix_revient', 'prix_vente_actuel', 'statut_obr', 'date_entree']
    list_filter   = ['societe', 'type_entree', 'statut_obr']
    search_fields = ['produit__designation', 'numero_ref', 'fournisseur__nom']
    date_hierarchy = 'date_entree'


@admin.register(SortieStock)
class SortieStockAdmin(admin.ModelAdmin):
    list_display  = ['societe', 'type_sortie', 'entree_stock', 'quantite', 'prix', 'statut_obr', 'date_sortie', 'actions_compenser']
    list_filter   = ['societe', 'type_sortie', 'statut_obr']
    search_fields = ['entree_stock__produit__designation', 'code']
    date_hierarchy = 'date_sortie'
    actions = ['compenser_selection_obr']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('entree_stock__produit', 'facture')

    def actions_compenser(self, obj):
        if obj.facture and obj.facture.statut_obr == 'ANNULE' and obj.statut_obr == 'ENVOYE':
            deja_compensee = EntreeStock.objects.filter(
                societe=obj.societe,
                produit=obj.entree_stock.produit,
                facture=obj.facture,
                type_entree='ER',
                commentaire__icontains="COMPENSATION"
            ).exists()
            if not deja_compensee:
                url = reverse('admin:compenser_sortie_obr', args=[obj.pk])
                return format_html(
                    '<a class="button" style="background:#ffc107;color:#000;padding:3px 8px;'
                    'border-radius:3px;text-decoration:none;font-size:11px;white-space:nowrap;" '
                    'href="{}" onclick="return confirm(\'Compenser cette sortie vers OBR ?\')">'
                    '<i class="bi bi-arrow-repeat"></i> Compenser OBR</a>',
                    url
                )
            return format_html('<span style="color:green;">Deja compensée</span>')
        return format_html('<span style="color:gray;">—</span>')
    actions_compenser.short_description = "Compensation OBR"
    actions_compenser.allow_tags = True

    def compenser_selection_obr(self, request, queryset):
        count_success = 0
        count_skip = 0
        count_error = 0

        for sortie in queryset.select_related('entree_stock__produit', 'facture'):
            if not sortie.facture or sortie.facture.statut_obr != 'ANNULE' or sortie.statut_obr != 'ENVOYE':
                count_skip += 1
                continue

            if EntreeStock.objects.filter(
                societe=sortie.societe,
                produit=sortie.entree_stock.produit,
                facture=sortie.facture,
                type_entree='ER',
                commentaire__icontains="COMPENSATION"
            ).exists():
                count_skip += 1
                continue

            try:
                with transaction.atomic():
                    entree = EntreeStock.objects.create(
                        societe=sortie.societe,
                        type_entree='ER',
                        numero_ref=f"COMP-{sortie.facture.numero}",
                        date_entree=timezone.now().date(),
                        produit=sortie.entree_stock.produit,
                        quantite=sortie.quantite,
                        prix_revient=Decimal(str(sortie.prix)),
                        prix_vente_actuel=sortie.prix,
                        devise=sortie.devise,
                        commentaire=f"COMPENSATION Stock OBR - Retour facture annulée {sortie.facture.display_numero}",
                        facture=sortie.facture,
                        statut_obr='EN_ATTENTE',
                    )

                success, msg = envoyer_entree_stock(entree)
                if success:
                    count_success += 1
                else:
                    count_error += 1
                    logger.warning(f"[ADMIN] Échec envoi OBR compensation sortie #{sortie.pk}: {msg}")

            except Exception as e:
                count_error += 1
                logger.exception(f"[ADMIN] Erreur compensation sortie #{sortie.pk}")

        msg_parts = []
        if count_success:
            msg_parts.append(f"{count_success} compensée(s) avec succès")
        if count_skip:
            msg_parts.append(f"{count_skip} ignorée(s)")
        if count_error:
            msg_parts.append(f"{count_error} erreur(s)")

        self.message_user(request, " | ".join(msg_parts) if msg_parts else "Aucune sortie à compenser.")
    compenser_selection_obr.short_description = "Compenser OBR les sorties sélectionnées (créer entrée retour ER)"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:sortie_id>/compenser-obr/',
                self.admin_site.admin_view(self.compenser_sortie_view),
                name='compenser_sortie_obr',
            ),
        ]
        return custom_urls + urls

    def compenser_sortie_view(self, request, sortie_id):
        sortie = get_object_or_404(
            SortieStock.objects.select_related('entree_stock__produit', 'facture'),
            pk=sortie_id
        )

        if not sortie.facture or sortie.facture.statut_obr != 'ANNULE':
            self.message_user(request, "Cette sortie n'est pas liée à une facture annulée.", level='ERROR')
            return redirect('admin:stock_sortiestock_changelist')

        if sortie.statut_obr != 'ENVOYE':
            self.message_user(request, "Cette sortie n'a pas été envoyée à l'OBR.", level='ERROR')
            return redirect('admin:stock_sortiestock_changelist')

        if EntreeStock.objects.filter(
            societe=sortie.societe,
            produit=sortie.entree_stock.produit,
            facture=sortie.facture,
            type_entree='ER',
            commentaire__icontains="COMPENSATION"
        ).exists():
            self.message_user(request, "Cette sortie a déjà été compensée.", level='INFO')
            return redirect('admin:stock_sortiestock_changelist')

        try:
            with transaction.atomic():
                entree = EntreeStock.objects.create(
                    societe=sortie.societe,
                    type_entree='ER',
                    numero_ref=f"COMP-{sortie.facture.numero}",
                    date_entree=timezone.now().date(),
                    produit=sortie.entree_stock.produit,
                    quantite=sortie.quantite,
                    prix_revient=Decimal(str(sortie.prix)),
                    prix_vente_actuel=sortie.prix,
                    devise=sortie.devise,
                    commentaire=f"COMPENSATION Stock OBR - Retour facture annulée {sortie.facture.display_numero}",
                    facture=sortie.facture,
                    statut_obr='EN_ATTENTE',
                )

            success, msg = envoyer_entree_stock(entree)
            if success:
                self.message_user(request, f"✅ Compensation OBR réussie : {msg}")
            else:
                self.message_user(request, f"⚠️ Entrée créée mais envoi OBR échoué : {msg}", level='WARNING')

        except Exception as e:
            logger.exception(f"Erreur compensation sortie #{sortie_id}")
            self.message_user(request, f"Erreur : {str(e)}", level='ERROR')

        return redirect('admin:stock_sortiestock_changelist')

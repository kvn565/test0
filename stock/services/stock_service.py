# stock/services/stock_service.py

from django.db import transaction
from stock.models import EntreeStock, SortieStock


def nettoyer_avant_nouvelle_entree(societe, produit=None):
    """Nettoie les anciens mouvements en attente/échec avant d'en créer un nouveau"""
    
    with transaction.atomic():
        # Nettoyage des entrées
        qs_entrees = EntreeStock.objects.filter(
            societe=societe,
            statut_obr__in=['EN_ATTENTE', 'ECHEC']
        )
        if produit:
            qs_entrees = qs_entrees.filter(produit=produit)

        # Nettoyage des sorties
        qs_sorties = SortieStock.objects.filter(
            societe=societe,
            statut_obr__in=['EN_ATTENTE', 'ECHEC']
        )
        # Si tu veux filtrer aussi par produit sur les sorties (souvent utile)
        if produit:
            qs_sorties = qs_sorties.filter(produit=produit)

        deleted_entrees = qs_entrees.count()
        deleted_sorties = qs_sorties.count()

        qs_entrees.delete()
        qs_sorties.delete()

        if deleted_entrees + deleted_sorties > 0:
            print(f"🧹 Nettoyage auto : {deleted_entrees} entrées + {deleted_sorties} sorties supprimées pour la société {societe}")

        return {
            'entrees_supprimees': deleted_entrees,
            'sorties_supprimees': deleted_sorties
        }
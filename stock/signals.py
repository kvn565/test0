# stock/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import EntreeStock, SortieStock


@receiver(post_save, sender='facturer.Facture')
def nettoyer_mouvements_stock_en_attente_sur_facture(sender, instance, created, **kwargs):
    if created:
        return

    statuts_annulation = ['ANNULEE', 'QUITTEE', 'ABANDONNEE', 'REJETEE']

    if getattr(instance, 'statut', None) in statuts_annulation:
        # Nettoyage via la méthode du Produit (plus propre)
        from produits.models import Produit
        
        # Nettoyer pour tous les produits concernés par cette facture
        for ligne in instance.lignes.all():          # ← Adaptez selon votre modèle de ligne
            if ligne.produit:
                ligne.produit.nettoyer_mouvements_facture(instance)
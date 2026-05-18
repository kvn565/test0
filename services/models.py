# services/models.py
from django.db import models
from decimal import Decimal
from societe.models import Societe
from taux.models import TauxTVA


class Service(models.Model):

    STATUT_CHOICES = [
        ('ACTIF', 'Actif'),
        ('INACTIF', 'Inactif'),
    ]

    societe       = models.ForeignKey(Societe, on_delete=models.CASCADE, related_name='services')
    designation   = models.CharField(max_length=200, verbose_name="Désignation")
    prix_vente    = models.DecimalField(max_digits=12, decimal_places=3, default=0, verbose_name="Prix de vente HT")
    
    taux_tva = models.ForeignKey(
        TauxTVA,
        on_delete=models.PROTECT,
        null=True,          # Gardé nullable pour l'instant
        blank=True,
        related_name='services',
        verbose_name="Taux TVA"
    )

    statut = models.CharField(max_length=10, choices=STATUT_CHOICES, default='ACTIF')

    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Service"
        verbose_name_plural = "Services"
        ordering = ['designation']
        unique_together = [('societe', 'designation')]

    def __str__(self):
        return f"{self.designation} ({self.taux_tva})"

    @property
    def tva_montant(self) -> Decimal:
        if not self.societe.applique_tva:
            return Decimal('0.000')
        tva = (self.prix_vente * self.taux_tva.valeur / Decimal('100'))
        return tva.quantize(Decimal('0.001'))

    @property
    def prix_vente_tvac(self) -> Decimal:
        return (self.prix_vente + self.tva_montant).quantize(Decimal('0.001'))
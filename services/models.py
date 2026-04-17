# services/models.py
from django.db import models
from societe.models import Societe
from taux.models import Taux


class Service(models.Model):

    STATUT_CHOICES = [
        ('ACTIF',   'Actif'),
        ('INACTIF', 'Inactif'),
    ]

    societe       = models.ForeignKey(Societe, on_delete=models.CASCADE, related_name='services')
    designation   = models.CharField(max_length=200, verbose_name="Désignation")
    prix_vente    = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Prix de vente")
    taux_tva      = models.ForeignKey(
        Taux, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='services', verbose_name="Taux TVA"
    )
    statut        = models.CharField(max_length=10, choices=STATUT_CHOICES, default='ACTIF', verbose_name="Statut")
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Service"
        verbose_name_plural = "Services"
        ordering            = ['designation']
        unique_together     = [('societe', 'designation')]

    def __str__(self):
        return self.designation

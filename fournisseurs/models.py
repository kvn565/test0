# fournisseurs/models.py
from django.db import models
from societe.models import Societe


class Fournisseur(models.Model):
    societe       = models.ForeignKey(Societe, on_delete=models.CASCADE, related_name='fournisseurs')
    nom           = models.CharField(max_length=150, verbose_name="Nom")
    adresse       = models.CharField(max_length=250, blank=True, verbose_name="Adresse")
    telephone     = models.CharField(max_length=20, blank=True, verbose_name="Téléphone")
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Fournisseur"
        verbose_name_plural = "Fournisseurs"
        ordering            = ['nom']
        unique_together     = [('societe', 'nom')]

    def __str__(self):
        return self.nom

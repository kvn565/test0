# taux/models.py
from django.db import models
from societe.models import Societe


class Taux(models.Model):
    societe       = models.ForeignKey(Societe, on_delete=models.CASCADE, related_name='taux')
    nom           = models.CharField(max_length=100, verbose_name="Nom")
    valeur        = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Valeur (%)")
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Taux TVA"
        verbose_name_plural = "Taux TVA"
        ordering            = ['valeur']
        unique_together     = [('societe', 'nom')]

    def __str__(self):
        return f"{self.nom} ({self.valeur} %)"

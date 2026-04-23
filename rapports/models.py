# rapports/models.py
from django.db import models
from django.contrib.auth import get_user_model
from societe.models import Societe

User = get_user_model()


class TypeRapport(models.TextChoices):
    ENTREES      = 'ENTREES',      'Entrées / Achats'
    COUT_STOCK   = 'COUT_STOCK',   'Coût du stock vendu'
    SORTIES      = 'SORTIES',      'Sorties / Ventes'
    STOCK_ACTUEL = 'STOCK_ACTUEL', 'Stock actuel'
    FACTURATION  = 'FACTURATION',  'Ventes / Facturation'


class Rapport(models.Model):

    societe = models.ForeignKey(
        Societe, on_delete=models.CASCADE,
        related_name='rapports', null=True, blank=True
    )
    type_rapport = models.CharField(
        max_length=30,
        choices=TypeRapport.choices,
        verbose_name="Type de rapport"
    )
    date_debut = models.DateField(
        null=True, blank=True,
        verbose_name="Date de début"
    )
    date_fin = models.DateField(
        null=True, blank=True,
        verbose_name="Date de fin"
    )
    fichier_pdf = models.FileField(
        upload_to='rapports/pdf/',
        null=True, blank=True,
        verbose_name="Fichier PDF"
    )
    fichier_excel = models.FileField(
        upload_to='rapports/excel/',
        null=True, blank=True,
        verbose_name="Fichier Excel"
    )
    cree_par = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Créé par"
    )
    date_creation = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création"
    )

    class Meta:
        ordering            = ['-date_creation']
        verbose_name        = "Rapport"
        verbose_name_plural = "Rapports"

    def __str__(self):
        return f"{self.get_type_rapport_display()} — {self.date_creation.strftime('%d/%m/%Y %H:%M')}"

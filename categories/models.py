# categories/models.py

from django.db import models
from societe.models import Societe


class Categorie(models.Model):
    """
    Catégorie de produits — liée à une société spécifique.

    ✅ CORRECTION : FK societe ajoutée.
       Sans cette FK, toutes les sociétés partageraient les mêmes catégories.
       Chaque société gère ses propres catégories indépendamment.
    """
    societe = models.ForeignKey(
        Societe,
        on_delete=models.CASCADE,
        related_name='categories',
        verbose_name="Société",
    )
    nom = models.CharField(max_length=100, verbose_name="Nom de la catégorie")
    description = models.TextField(blank=True, verbose_name="Description")
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    obr_mode_envoye = models.BooleanField(default=False, verbose_name="Mode PRODUCTION", editable=False)

    class Meta:
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"
        ordering = ['nom']
        unique_together = [('societe', 'nom')]

    def __str__(self):
        return self.nom

    @property
    def nb_produits(self):
        return self.produits.count()

    def save(self, *args, **kwargs):
        if not self.pk and getattr(self, 'societe', None):
            self.obr_mode_envoye = self.societe.obr_mode_production
        super().save(*args, **kwargs)

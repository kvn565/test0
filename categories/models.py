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

    class Meta:
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"
        ordering = ['nom']
        # Deux catégories ne peuvent pas avoir le même nom dans la même société
        unique_together = [('societe', 'nom')]

    def __str__(self):
        return self.nom

    @property
    def nb_produits(self):
        """Nombre de produits dans cette catégorie."""
        return self.produits.count()

# clients/models.py

from django.db import models
from societe.models import Societe


class TypeClient(models.Model):
    """
    Type de client — lié à une société spécifique.

    ✅ CORRECTION : FK societe ajoutée.
       Chaque société définit ses propres types (Particulier, Entreprise, ONG...).
    """
    societe = models.ForeignKey(
        Societe,
        on_delete=models.CASCADE,
        related_name='types_clients',
        verbose_name="Société",
    )
    nom = models.CharField(max_length=100, verbose_name="Type de client")

    class Meta:
        verbose_name = "Type de client"
        verbose_name_plural = "Types de clients"
        ordering = ['nom']
        # Pas deux types identiques dans la même société
        unique_together = [('societe', 'nom')]

    def __str__(self):
        return self.nom

    @property
    def nb_clients(self):
        return self.clients.count()


class Client(models.Model):
    """
    Client d'une société — lié à une société spécifique.

    ✅ CORRECTION : FK societe ajoutée.
       Un client appartient à une seule société.
    """
    societe = models.ForeignKey(
        Societe,
        on_delete=models.CASCADE,
        related_name='clients',
        verbose_name="Société",
    )
    type_client = models.ForeignKey(
        TypeClient,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='clients',
        verbose_name="Type de client",
    )
    nom          = models.CharField(max_length=150, verbose_name="Nom du client")
    nif          = models.CharField(max_length=50, blank=True, null=True, verbose_name="NIF")
    assujeti_tva = models.BooleanField(default=False, verbose_name="Assujetti TVA")
    adresse      = models.CharField(max_length=200, blank=True, null=True, verbose_name="Adresse / Résidence")
    date_creation = models.DateField(auto_now_add=True)

    class Meta:
        verbose_name = "Client"
        verbose_name_plural = "Clients"
        ordering = ['nom']

    def __str__(self):
        # ✅ CORRIGÉ : évite le crash si type_client est None (SET_NULL)
        type_str = f" ({self.type_client.nom})" if self.type_client else ""
        return f"{self.nom}{type_str}"

    @property
    def nb_factures(self):
        """Nombre de factures associées à ce client."""
        return self.factures.count() if hasattr(self, 'factures') else 0

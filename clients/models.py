from django.db import models
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver

from societe.models import Societe   # ou from .models import Societe si c'est le même fichier


class TypeClient(models.Model):
    """
    Type de client propre à chaque société.
    Par défaut : Particulier, Société locale, Société étrangère
    """
    societe = models.ForeignKey(
        Societe,
        on_delete=models.CASCADE,
        related_name='types_clients',
        verbose_name="Société",
    )
    nom = models.CharField(max_length=100, verbose_name="Type de client")
    est_defaut = models.BooleanField(default=False, verbose_name="Type par défaut")

    class Meta:
        verbose_name = "Type de client"
        verbose_name_plural = "Types de clients"
        ordering = ['nom']
        unique_together = [('societe', 'nom')]   # Un type par société

    def __str__(self):
        return self.nom

    @property
    def nb_clients(self):
        return self.clients.count()


class Client(models.Model):
    """
    Client d'une société — préparé pour conformité OBR / eBMS
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

    # ── Champs principaux ────────────────────────────────────────────────
    nom = models.CharField(max_length=150, verbose_name="Nom / Raison sociale du client")
    
    nif = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="NIF",
        help_text="Numéro d'Identification Fiscale"
    )

    assujeti_tva = models.BooleanField(
        default=False,
        verbose_name="Assujetti à la TVA"
    )

    # ── Adresse ─────────────────────────────────────────────────────────
    adresse = models.CharField(max_length=200, blank=True, null=True, verbose_name="Adresse complète")
    province = models.CharField(max_length=100, blank=True, null=True)
    commune = models.CharField(max_length=100, blank=True, null=True)
    quartier = models.CharField(max_length=100, blank=True, null=True)
    avenue = models.CharField(max_length=100, blank=True, null=True)
    numero = models.CharField(max_length=20, blank=True, null=True)

    telephone = models.CharField(max_length=30, blank=True, null=True, verbose_name="Téléphone")

    # ── Champs OBR ───────────────────────────────────────────────────────
    verifie_obr = models.BooleanField(default=False, verbose_name="Vérifié par OBR")
    date_verification = models.DateTimeField(null=True, blank=True)
    nom_obr_officiel = models.CharField(max_length=150, blank=True, null=True)

    # ── Traçabilité ──────────────────────────────────────────────────────
    cree_par = models.ForeignKey(
        'superadmin.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='clients_crees'
    )
    date_creation = models.DateTimeField(default=timezone.now)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Client"
        verbose_name_plural = "Clients"
        ordering = ['nom']
        unique_together = [('societe', 'nif')]

    def __str__(self):
        return f"{self.nom} ({self.type_client.nom if self.type_client else 'Sans type'})"

    @property
    def vat_customer_payer(self):
        return "1" if self.assujeti_tva else "0"

    @property
    def adresse_complete(self):
        parts = [p for p in [self.adresse, self.avenue, f"N°{self.numero}" if self.numero else None,
                             self.quartier, self.commune, self.province] if p]
        return ", ".join(parts) if parts else "—"


# ====================== SIGNAL POUR CRÉER LES TYPES PAR DÉFAUT ======================

@receiver(post_save, sender=Societe)
def creer_types_clients_par_defaut(sender, instance, created, **kwargs):
    """
    Crée automatiquement les 3 types de clients par défaut 
    lorsqu'une nouvelle société est créée.
    """
    if created:  # Seulement à la création de la société
        types_defaut = [
            {"nom": "Particulier", "est_defaut": True},
            {"nom": "Société locale", "est_defaut": True},
            {"nom": "Société étrangère", "est_defaut": True},
        ]

        for t in types_defaut:
            TypeClient.objects.get_or_create(
                societe=instance,
                nom=t["nom"],
                defaults={"est_defaut": t["est_defaut"]}
            )
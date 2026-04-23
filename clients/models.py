from django.db import models
from django.utils import timezone
from societe.models import Societe


class TypeClient(models.Model):
    """
    Type de client propre à chaque société.
    Ex: Particulier, Entreprise, ONG, Administration, etc.
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
        unique_together = [('societe', 'nom')]   # Un type par société

    def __str__(self):
        return f"{self.nom} ({self.societe.nom})"

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
        help_text="Numéro d'Identification Fiscale (vérifiable via checkTIN)"
    )

    assujeti_tva = models.BooleanField(
        default=False,
        verbose_name="Assujetti à la TVA",
        help_text="Correspond à vat_customer_payer dans l'API OBR"
    )

    # ── Adresse ─────────────────────────────────────────────────────────
    adresse = models.CharField(max_length=200, blank=True, null=True, verbose_name="Adresse complète")
    province = models.CharField(max_length=100, blank=True, null=True)
    commune = models.CharField(max_length=100, blank=True, null=True)
    quartier = models.CharField(max_length=100, blank=True, null=True)
    avenue = models.CharField(max_length=100, blank=True, null=True)
    numero = models.CharField(max_length=20, blank=True, null=True, verbose_name="Numéro")

    telephone = models.CharField(max_length=30, blank=True, null=True, verbose_name="Téléphone")

    # ── Champs OBR ───────────────────────────────────────────────────────
    verifie_obr = models.BooleanField(default=False, verbose_name="Vérifié par OBR")
    date_verification = models.DateTimeField(null=True, blank=True, verbose_name="Date de vérification OBR")
    nom_obr_officiel = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        verbose_name="Nom officiel retourné par OBR",
        help_text="Ne pas modifier manuellement"
    )

    # ── Traçabilité ──────────────────────────────────────────────────────
    cree_par = models.ForeignKey(
        'superadmin.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='clients_crees',
        verbose_name="Créé par"
    )
    date_creation = models.DateTimeField(default=timezone.now, verbose_name="Date de création")
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Client"
        verbose_name_plural = "Clients"
        ordering = ['nom']
        unique_together = [
            ('societe', 'nif'),      # Un même NIF ne peut exister qu'une fois par société
        ]

    def __str__(self):
        nif_str = f" — NIF {self.nif}" if self.nif else ""
        type_str = f" ({self.type_client.nom})" if self.type_client else ""
        return f"{self.nom}{type_str}{nif_str}"

    @property
    def vat_customer_payer(self):
        """Valeur attendue par l'API OBR (addInvoice)"""
        return "1" if self.assujeti_tva else "0"

    @property
    def adresse_complete(self):
        parts = []
        if self.adresse:
            parts.append(self.adresse)
        elif self.avenue or self.numero or self.quartier or self.commune:
            if self.avenue:
                parts.append(self.avenue)
            if self.numero:
                parts.append(f"N° {self.numero}")
            if self.quartier:
                parts.append(self.quartier)
            if self.commune:
                parts.append(self.commune)
            if self.province:
                parts.append(self.province)
        return ", ".join(parts) if parts else "—"

    def marquer_comme_verifie_obr(self, nom_officiel: str):
        """Méthode utilitaire après un checkTIN réussi"""
        self.nom_obr_officiel = nom_officiel.strip()
        self.verifie_obr = True
        self.date_verification = timezone.now()
        self.save(update_fields=['nom_obr_officiel', 'verifie_obr', 'date_verification'])
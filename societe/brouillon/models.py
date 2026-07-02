# societe/models.py — VERSION CORRIGÉE (changements minimaux)
from django.db import models
from django.utils import timezone
from decimal import Decimal


class Societe(models.Model):

    CENTRE_FISCALE_CHOICES = [
        ('DGC',    'DGC — Direction Générale des Contributions'),
        ('DMC',    'DMC — Direction des Moyennes Contributions'),
        ('DPMC',   'DPMC — Direction des Petites et Moyennes Contributions'),
        ('PRIVEE', 'Société Privée'),
        ('SU',     'SU — Service des Unités'),
    ]

    # ── Champs saisis par le SUPERADMIN ────────────────────────────────
    nom = models.CharField(max_length=200, verbose_name="Nom de la société")
    nif = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="NIF",
        help_text="Doit être exact. Le chef ne pourra s'inscrire qu'avec ce NIF.",
    )

    # ── Champs complétés par le CHEF lors de l'inscription ─────
    registre      = models.CharField(max_length=100, blank=True, default='', verbose_name="Registre de commerce")
    boite_postal  = models.CharField(max_length=50, blank=True, null=True, verbose_name="Boîte postale")
    telephone     = models.CharField(max_length=50, blank=True, default='', verbose_name="Téléphone")
    email_societe = models.EmailField(max_length=254, blank=True, verbose_name="Email de la société")

    logo = models.ImageField(
        verbose_name="Logo de la société",
        upload_to='logos/',
        blank=True,
        null=True,
    )

    facture_logo = models.ImageField(
        upload_to='factures/logos/',
        blank=True,
        null=True,
        verbose_name="Logo / Photo d'en-tête de facture",
        help_text="Image qui apparaîtra en haut des factures (taille recommandée : 800x250 px)"
    )

    facture_pied_page = models.TextField(
        blank=True,
        default='',
        verbose_name="Pied de page de facture",
        help_text="Texte qui apparaîtra en bas de chaque facture (mentions légales, RIB, etc.)"
    )

    # Champs métier
    secteur = models.CharField(max_length=250, blank=True, default='', verbose_name="Secteur d'activité")
    forme   = models.CharField(max_length=50,  blank=True, default='', verbose_name="Forme juridique")

    # Adresse
    province = models.CharField(max_length=100, blank=True, default='', verbose_name="Province")
    commune  = models.CharField(max_length=100, blank=True, default='', verbose_name="Commune")
    quartier = models.CharField(max_length=100, blank=True, default='', verbose_name="Quartier")
    avenue   = models.CharField(max_length=150, blank=True, default='', verbose_name="Avenue")
    numero   = models.CharField(max_length=20, blank=True, null=True, verbose_name="Numéro")

    # Fiscalité
    centre_fiscale = models.CharField(
        max_length=10,
        blank=True,
        choices=CENTRE_FISCALE_CHOICES,
        verbose_name="Centre fiscal"
    )

    assujeti_tva = models.BooleanField(default=False, verbose_name="Assujetti à la TVA")
    assujeti_tc  = models.BooleanField(default=False, verbose_name="Assujetti à la Taxe de Consommation (TC)")
    assujeti_pfl = models.BooleanField(default=False, verbose_name="Assujetti au Prélèvement Forfaitaire Libératoire (PFL)")

    # Champs OBR
    obr_username  = models.CharField(max_length=100, blank=True, default='', verbose_name="Nom d'utilisateur OBR")
    obr_password  = models.CharField(max_length=100, blank=True, default='', verbose_name="Mot de passe OBR")
    obr_system_id = models.CharField(max_length=100, blank=True, default='', verbose_name="Identifiant système OBR")

    obr_base_url = models.URLField(
        verbose_name="URL API OBR (personnalisée)",
        max_length=255,
        blank=True,
        null=True,
        default="https://ebms.obr.gov.bi:9443/ebms_api",
        help_text="Laisser vide pour utiliser par défaut"
    )

    obr_actif = models.BooleanField(default=False, verbose_name="Intégration OBR activée")

    obr_mode_production = models.BooleanField(
        default=False,
        verbose_name="Mode PRODUCTION",
        help_text="Décochez pour Test (9443) | Cochez pour Production (8443)"
    )

    # Champs admin
    numero_depart      = models.PositiveIntegerField(default=1, verbose_name="Numéro de départ facture")
    nom_complet_gerant = models.CharField(max_length=200, blank=True, verbose_name="Nom complet du gérant")

    # Traçabilité
    date_creation     = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Société"
        verbose_name_plural = "Sociétés"
        ordering            = ['nom']

    def __str__(self):
        return f"{self.nom} (NIF: {self.nif})"

    # ── Adresse ─────────────────────────────────────────────────────────
    @property
    def adresse_complete(self):
        parts = [p for p in [
            self.avenue,
            f"N°{self.numero}" if self.numero else None,
            self.quartier,
            self.commune,
            self.province
        ] if p]
        return ', '.join(parts)

    # ── Licence ─────────────────────────────────────────────────────────
    @property
    def cle_active(self):
        today = timezone.localdate()
        return self.cles_activation.filter(
            statut__in=['ACTIVE', 'DISPONIBLE'],
            active=True,
            date_fin__date__gte=today,
        ).order_by('-date_creation').first()

    @property
    def licence_valide(self):
        return self.cle_active is not None

    # ── Utilisateurs ────────────────────────────────────────────────────
    @property
    def chef(self):
        return self.utilisateurs.filter(type_poste='DIRECTEUR').first()

    @property
    def inscription_complete(self):
        return self.utilisateurs.filter(type_poste='DIRECTEUR').exists()

    # ── Complétude ──────────────────────────────────────────────────────
    @property
    def infos_completes(self):
        return all([
            self.registre,
            self.telephone,
            self.province,
            self.commune,
            self.quartier,
            self.avenue,
            self.centre_fiscale,
            self.secteur,
            self.forme,
        ])

    @property
    def obr_configure(self):
        return bool(self.obr_username and self.obr_password and self.obr_system_id)

    @property
    def infos_obr_completes(self):
        return bool(
            self.nom and self.nif and self.centre_fiscale and
            self.secteur and self.forme and self.telephone and
            self.commune and self.quartier and self.avenue
        )

    # ── TVA ─────────────────────────────────────────────────────────────
    @property
    def applique_tva(self):
        """Utilisé par le module Facture"""
        return self.assujeti_tva

    # ── Facture ─────────────────────────────────────────────────────────
    @property
    def pied_page_facture(self):
        return self.facture_pied_page.strip()

    # ── OBR ─────────────────────────────────────────────────────────────
    def get_tp_type(self):
        return "2"

    def get_vat_taxpayer(self):
        return "1" if self.assujeti_tva else "0"

    def get_ct_taxpayer(self):
        return "1" if self.assujeti_tc else "0"

    def get_tl_taxpayer(self):
        return "1" if self.assujeti_pfl else "0"

    def get_tp_fiscal_center(self):
        mapping = {
            'DGC':    'DGC',
            'DMC':    'DMC',
            'DPMC':   'DPMC',
            'PRIVEE': 'DMC',
            'SU':     'DPMC',
        }
        return mapping.get(self.centre_fiscale, 'DMC')
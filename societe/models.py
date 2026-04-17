# societe/models.py — VERSION CORRIGÉE (focus : données du chef bien stockées et complètes)

from django.db import models
from django.utils import timezone


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

    # ── Champs complétés par le CHEF lors de l'inscription (/setup/) ─────
    registre      = models.CharField(max_length=100, blank=True, default='', verbose_name="Registre de commerce")
    boite_postal  = models.CharField(max_length=50, blank=True, null=True, verbose_name="Boîte postale")
    telephone     = models.CharField(max_length=50, blank=True, default='', verbose_name="Téléphone")
    email_societe = models.EmailField(max_length=254, blank=True, verbose_name="Email de la société")

    # Logo (rempli par le chef)
    logo = models.ImageField(
        verbose_name="Logo de la société",
        upload_to='logos/',
        blank=True,
        null=True,
    )

    # Champs métier remplis par le chef
    secteur = models.CharField(max_length=250, blank=True, default='', verbose_name="Secteur d'activité")
    forme   = models.CharField(max_length=50,  blank=True, default='', verbose_name="Forme juridique")

    # Adresse (très importante pour l'OBR — remplie par le chef)
    province = models.CharField(max_length=100, blank=True, default='', verbose_name="Province")
    commune  = models.CharField(max_length=100, blank=True, default='', verbose_name="Commune")
    quartier = models.CharField(max_length=100, blank=True, default='', verbose_name="Quartier")
    avenue   = models.CharField(max_length=150, blank=True, default='', verbose_name="Avenue")
    numero   = models.CharField(max_length=20, blank=True, null=True, verbose_name="Numéro")

    # ── Fiscalité (remplie par le chef — conforme OBR) ─────────────────
    centre_fiscale = models.CharField(
        max_length=10,
        blank=True,
        choices=CENTRE_FISCALE_CHOICES,
        verbose_name="Centre fiscal",
        help_text="DGC, DMC, DPMC, PRIVEE, SU"
    )

    assujeti_tva = models.BooleanField(default=False, verbose_name="Assujetti à la TVA")
    assujeti_tc  = models.BooleanField(default=False, verbose_name="Assujetti à la Taxe de Consommation (TC)")
    assujeti_pfl = models.BooleanField(default=False, verbose_name="Assujetti au Prélèvement Forfaitaire Libératoire (PFL)")

    # ── Champs OBR — Configurés par le SUPERADMIN uniquement ───────────
    obr_username  = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name="Nom d'utilisateur OBR",
        help_text="Identifiant fourni par l'OBR pour l'accès à l'API eBMS.",
    )
    obr_password  = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name="Mot de passe OBR",
        help_text="Mot de passe fourni par l'OBR pour l'API eBMS.",
    )
    obr_system_id = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name="Identifiant système OBR",
        help_text="Ex: ws440077324400027 — fourni par l'OBR avec le mot de passe.",
    )
    obr_actif = models.BooleanField(
        default=False,
        verbose_name="Intégration OBR activée",
        help_text="Activer l'envoi automatique des données à l'OBR.",
    )

    # ── Champs admin ───────────────────────────────────────────────────
    numero_depart = models.PositiveIntegerField(
        default=1,  # changé de 0 à 1 (plus logique)
        verbose_name="Numéro de départ facture",
        help_text="Numéro à partir duquel la séquence des factures commence."
    )

    nom_complet_gerant = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Nom complet du gérant",
        help_text="Nom complet du gérant de la société."
    )

    # ── Traçabilité ────────────────────────────────────────────────────
    date_creation     = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Société"
        verbose_name_plural = "Sociétés"
        ordering            = ['nom']

    def __str__(self):
        return f"{self.nom} (NIF: {self.nif})"

    # ====================== PROPRIÉTÉS CORRIGÉES ======================

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

    @property
    def cle_active(self):
        now = timezone.now()
        return self.cles_activation.filter(
            statut='ACTIVE',                    # Après activation par le chef
            date_fin__gte=now
        ).order_by('-date_creation').first()

    @property
    def licence_valide(self):
        return self.cle_active is not None

    @property
    def chef(self):
        return self.utilisateurs.filter(type_poste='DIRECTEUR').first()

    @property
    def inscription_complete(self):
        return self.utilisateurs.filter(type_poste='DIRECTEUR').exists()

    @property
    def infos_completes(self):
        """Vérifie que le chef a bien rempli les informations essentielles"""
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

    # ====================== MÉTHODES OBR (utilisées lors de l'envoi) ======================

    def get_tp_type(self):
        """Toujours '2' pour une société (personne morale)"""
        return "2"

    def get_vat_taxpayer(self):
        return "1" if self.assujeti_tva else "0"

    def get_ct_taxpayer(self):
        return "1" if self.assujeti_tc else "0"

    def get_tl_taxpayer(self):
        return "1" if self.assujeti_pfl else "0"

    def get_tp_fiscal_center(self):
        mapping = {
            'DGC': 'DGC',
            'DMC': 'DMC',
            'DPMC': 'DPMC',
            'PRIVEE': 'DMC',
            'SU': 'DPMC',
        }
        return mapping.get(self.centre_fiscale, 'DMC')

    @property
    def infos_obr_completes(self):
        """Vérifie si les infos minimales exigées par l'API eBMS sont présentes"""
        return bool(
            self.nom and self.nif and self.centre_fiscale and
            self.secteur and self.forme and self.telephone and
            self.commune and self.quartier and self.avenue
        )
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal

from societe.models import Societe
from clients.models import Client
from produits.models import Produit
from services.models import Service


class Facture(models.Model):
    TYPE_CHOICES = [
        ('FN', 'FN — Facture Normale'),
        ('FA', 'FA — Facture Avoir / Note de Crédit'),
    ]
    DEVISE_CHOICES = [
        ('BIF', 'BIF — Franc Burundais'),
        ('USD', 'USD — Dollar Américain'),
        ('EUR', 'EUR — Euro'),
    ]
    MODE_PAIEMENT_CHOICES = [
        ('CAISSE', 'Caisse'),
        ('BANQUE', 'Banque'),
        ('CREDIT', 'Crédit'),
        ('AUTRES', 'Autres'),
    ]
    STATUT_OBR_CHOICES = [
        ('EN_ATTENTE', 'En attente'),
        ('ENVOYE',     'Envoyé OBR'),
        ('ECHEC',      'Échec envoi'),
        ('ANNULE',     'Annulé OBR'),
    ]

    societe = models.ForeignKey(
        Societe,
        on_delete=models.CASCADE,
        related_name='factures',
        verbose_name="Société",
    )

    numero = models.CharField(
        max_length=50,
        blank=True,
        editable=False,
        verbose_name="N° Facture",
        help_text="Format stocké : FN/2/2026 (type/séquence/année)",
    )

    invoice_identifier = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        unique=True,
        verbose_name="Identifiant facture OBR",
    )

    date_facture = models.DateField(default=timezone.now, verbose_name="Date")
    heure_facture = models.TimeField(default=timezone.now, verbose_name="Heure")
    type_facture = models.CharField(max_length=5, choices=TYPE_CHOICES, default='FN', verbose_name="Type")

    facture_originale = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='avoirs_lies',
        verbose_name="Facture originale",
        help_text="Obligatoire pour les avoirs (FA)",
    )
    motif_avoir = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="Motif de l'avoir",
    )

    bon_commande = models.CharField(max_length=100, blank=True, null=True, verbose_name="Bon de commande")
    client = models.ForeignKey(
        Client,
        on_delete=models.PROTECT,
        related_name='factures',
        verbose_name="Client",
    )

    devise = models.CharField(max_length=5, choices=DEVISE_CHOICES, default='BIF', verbose_name="Devise")
    mode_paiement = models.CharField(max_length=10, choices=MODE_PAIEMENT_CHOICES, default='CAISSE', verbose_name="Mode de paiement")

    total_ht  = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)
    total_tva = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)
    total_ttc = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)

    statut_obr = models.CharField(max_length=20, choices=STATUT_OBR_CHOICES, default='EN_ATTENTE', editable=False)
    message_obr = models.TextField(blank=True, editable=False)
    date_envoi_obr = models.DateTimeField(null=True, blank=True, editable=False)
    obr_registered_number = models.CharField(max_length=50, blank=True, null=True, editable=False)
    obr_registered_date = models.DateTimeField(null=True, blank=True, editable=False)
    electronic_signature = models.TextField(blank=True, editable=False)
    qr_code_image = models.ImageField(upload_to='qrcodes/factures/', blank=True, null=True)

    cree_par = models.ForeignKey(
        'superadmin.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        related_name='factures_creees',
        verbose_name="Créée par",
        editable=False,
    )
    date_creation = models.DateTimeField(auto_now_add=True, editable=False)
    date_annulation = models.DateTimeField(null=True, blank=True)

    # ==================== CHAMPS AJOUTÉS POUR LA GESTION DES ABANDONS ====================
    date_expiration = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name="Date d'expiration (nettoyage auto)"
    )

    est_abandonnee = models.BooleanField(
        default=False,
        verbose_name="Facture abandonnée"
    )

    class Meta:
        verbose_name = "Facture"
        verbose_name_plural = "Factures"
        ordering = ['-date_creation']
        unique_together = [('societe', 'numero')]
        indexes = [
            models.Index(fields=['societe', 'type_facture', 'date_facture']),
            models.Index(fields=['societe', 'statut_obr', 'date_creation']),
            models.Index(fields=['societe', 'est_abandonnee', 'date_expiration']),
        ]

    def __str__(self):
        return f"{self.display_numero} — {self.client.nom if self.client else '(client manquant)'}"

    @property
    def display_numero(self):
        """Affiche : FN/2/2026"""
        return self.numero if self.numero else f"{self.type_facture}/(non généré)"

    @property
    def numero_obr(self):
        if self.numero:
            return self.numero.strip()
        return f"{self.type_facture}/0/{timezone.now().year}"

    def get_starting_sequence(self) -> int:
        if hasattr(self.societe, 'numero_depart') and self.societe.numero_depart > 0:
            return self.societe.numero_depart
        return 1

    def get_last_sequence(self) -> int:
        year = self.date_facture.year if self.date_facture else timezone.now().year

        last = Facture.objects.filter(
            societe=self.societe,
            type_facture=self.type_facture,
            date_facture__year=year,
        ).exclude(pk=self.pk).order_by('-numero').first()

        if not last or not last.numero or '/' not in last.numero:
            return self.get_starting_sequence() - 1

        try:
            parts = last.numero.split('/')
            return int(parts[1]) if len(parts) >= 2 else self.get_starting_sequence() - 1
        except (ValueError, IndexError):
            return self.get_starting_sequence() - 1

    def generate_numero(self):
        if self.numero:
            return

        year = self.date_facture.year if self.date_facture else timezone.now().year
        last_seq = self.get_last_sequence()
        new_seq = last_seq + 1

        self.numero = f"{self.type_facture}/{new_seq}/{year}"

    def generate_invoice_identifier(self):
        if not self.societe:
            raise ValueError("Société requise pour générer l'identifiant OBR")

        system_id = (getattr(self.societe, "obr_system_id", "") or "").strip()
        company_nif = (getattr(self.societe, "nif", "") or "").strip()

        if not system_id:
            raise ValueError("obr_system_id non configuré pour cette société")
        if not company_nif:
            raise ValueError("NIF non configuré pour cette société")

        now = timezone.now()
        datetime_str = now.strftime("%Y%m%d%H%M%S")

        self.invoice_identifier = (
            f"{company_nif}/"
            f"{system_id}/"
            f"{datetime_str}/"
            f"{self.numero_obr}"
        )[:150]

    def clean(self):
        if self.type_facture == 'FA':
            if not self.facture_originale:
                raise ValidationError({"facture_originale": "Une facture d'avoir doit référencer une facture originale."})
            if not self.motif_avoir.strip():
                raise ValidationError({"motif_avoir": "Le motif de l'avoir est obligatoire pour une FA."})
            if self.total_ttc and self.facture_originale.total_ttc:
                if self.total_ttc > self.facture_originale.total_ttc:
                    raise ValidationError({"total_ttc": "Le montant TTC d'un avoir ne peut dépasser celui de la facture originale."})

        if self.total_ttc < 0:
            raise ValidationError({"total_ttc": "Le total TTC ne peut pas être négatif."})

    def save(self, *args, **kwargs):
        if not self.societe_id:
            raise ValueError("La société doit être définie avant sauvegarde.")

        # === MODIFICATIONS MINIMALES AJOUTÉES ===
        if self.statut_obr == 'EN_ATTENTE' and not self.date_expiration:
            self.date_expiration = timezone.now() + timezone.timedelta(hours=2)

        # Ne générer le numéro et l'identifiant OBR que lorsqu'on valide la facture
        if not self.numero and self.statut_obr != 'EN_ATTENTE':
            self.generate_numero()

        if not self.invoice_identifier and self.statut_obr != 'EN_ATTENTE':
            try:
                self.generate_invoice_identifier()
            except Exception:
                pass

        super().save(*args, **kwargs)

        # Recalcul des totaux seulement si la facture a des lignes
        if self.pk and self.lignes.exists():
            self.recalculer_totaux()

    def recalculer_totaux(self):
        lignes = self.lignes.all()

        total_ht = Decimal('0')
        total_tva = Decimal('0')
        total_ttc = Decimal('0')

        for ligne in lignes:
            total_ht += ligne.montant_ht
            total_tva += ligne.montant_tva
            total_ttc += ligne.montant_ttc

        Facture.objects.filter(pk=self.pk).update(
            total_ht=total_ht.quantize(Decimal('0.01')),
            total_tva=total_tva.quantize(Decimal('0.01')),
            total_ttc=total_ttc.quantize(Decimal('0.01')),
        )

        self.refresh_from_db(fields=['total_ht', 'total_tva', 'total_ttc'])

    @property
    def montant_en_lettres(self):
        try:
            from num2words import num2words
            montant = int(round(self.total_ttc))
            devise_text = "francs burundais" if self.devise == "BIF" else self.devise.lower()
            return num2words(montant, lang='fr').capitalize() + f" {devise_text}."
        except Exception:
            return f"{self.total_ttc} {self.devise}"

    @property
    def est_envoyee_obr(self):
        return self.statut_obr in ('ENVOYE', 'ANNULE')

    @property
    def peut_etre_supprimee(self):
        return self.statut_obr == 'EN_ATTENTE' and not self.est_abandonnee

    # Dans facturer/models.py → classe Facture
    def nettoyer_mouvements_stock(self):
        """Nettoie les mouvements de stock EN_ATTENTE selon le type de facture"""
        from stock.models import SortieStock, EntreeStock
        from django.db import transaction

        with transaction.atomic():
            if self.type_facture == 'FN':
                deleted = SortieStock.objects.filter(
                    facture=self,
                    statut_obr='EN_ATTENTE'
                ).delete()[0]
                action = f"{deleted} sortie(s) supprimée(s)"

            elif self.type_facture == 'FA':
                deleted = EntreeStock.objects.filter(
                    facture=self,
                    statut_obr='EN_ATTENTE'
                ).delete()[0]
                action = f"{deleted} entrée retour supprimée(s)"

            else:
                action = "Aucun mouvement stock concerné"

            return action


# ==================== Modèles inchangés ====================
class LigneFacture(models.Model):
    facture         = models.ForeignKey(Facture, on_delete=models.CASCADE, related_name='lignes')
    produit         = models.ForeignKey(Produit, on_delete=models.PROTECT, null=True, blank=True)
    service         = models.ForeignKey(Service, on_delete=models.PROTECT, null=True, blank=True)
    designation     = models.CharField(max_length=250, verbose_name="Désignation")
    quantite_stock  = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Qté en stock")
    taux_tva        = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="TVA %")
    prix_vente_tvac = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Prix TVAC")
    quantite        = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Qté vendue")

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.designation

    @property
    def prix_ht(self):
        if self.taux_tva > 0:
            return (self.prix_vente_tvac / (Decimal('1') + self.taux_tva / Decimal('100'))).quantize(Decimal('0.01'))
        return self.prix_vente_tvac

    @property
    def montant_ht(self):
        return (self.prix_ht * self.quantite).quantize(Decimal('0.01'))

    @property
    def montant_tva(self):
        return (self.montant_ht * self.taux_tva / Decimal('100')).quantize(Decimal('0.01'))

    @property
    def montant_ttc(self):
        return (self.montant_ht + self.montant_tva).quantize(Decimal('0.01'))


class FacturePendingOBR(models.Model):
    facture = models.ForeignKey(Facture, on_delete=models.CASCADE, related_name='pending_obr')
    payload = models.JSONField(blank=True, null=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    statut = models.CharField(max_length=50, default='EN_ATTENTE')
    message = models.TextField(blank=True, null=True)
    retry_count = models.PositiveIntegerField(default=0, verbose_name="Nombre de tentatives")

    class Meta:
        verbose_name = "Facture en attente OBR"
        verbose_name_plural = "Factures en attente OBR"

    def __str__(self):
        return f"Pending OBR — {self.facture.display_numero} ({self.statut})"
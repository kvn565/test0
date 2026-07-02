from decimal import Decimal, ROUND_DOWN
from datetime import timedelta, date

from django.db import models, transaction
from django.utils import timezone

from societe.models import Societe
from clients.models import Client
from produits.models import Produit
from services.models import Service
from taux.models import TauxTVA


class Devis(models.Model):
    STATUT_CHOICES = [
        ('BROUILLON', 'Brouillon'),
        ('EN_ATTENTE', 'En attente'),
        ('VALIDE', 'Validé'),
        ('REFUSE', 'Refusé'),
        ('EXPIRE', 'Expiré'),
        ('TRANSFORME', 'Transformé en facture'),
    ]
    DEVISE_CHOICES = [
        ('BIF', 'BIF — Franc Burundais'),
        ('USD', 'USD — Dollar Américain'),
        ('EUR', 'EUR — Euro'),
    ]

    societe = models.ForeignKey(Societe, on_delete=models.CASCADE, related_name='devis', verbose_name="Société")
    numero = models.CharField(max_length=50, blank=True, editable=False, verbose_name="N° Proforma")
    uuid_public = models.CharField(max_length=64, blank=True, editable=False, verbose_name="UUID public", db_index=True)

    date_devis = models.DateField(default=timezone.now, verbose_name="Date")
    date_validite = models.DateField(verbose_name="Valable jusqu'au")
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='devis', verbose_name="Client")
    devise = models.CharField(max_length=5, choices=DEVISE_CHOICES, default='BIF', verbose_name="Devise")
    applique_tva = models.BooleanField(default=True, verbose_name="Appliquer la TVA")

    total_ht = models.DecimalField(max_digits=14, decimal_places=3, default=0, editable=False)
    total_tva = models.DecimalField(max_digits=14, decimal_places=3, default=0, editable=False)
    total_ttc = models.DecimalField(max_digits=14, decimal_places=3, default=0, editable=False)

    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='BROUILLON')
    notes = models.TextField(blank=True, verbose_name="Notes / Conditions")
    email_envoye = models.BooleanField(default=False, verbose_name="Email envoyé au client")

    cree_par = models.ForeignKey('superadmin.Utilisateur', on_delete=models.SET_NULL, null=True,
                                 related_name='devis_creees', verbose_name="Créé par", editable=False)
    date_creation = models.DateTimeField(auto_now_add=True, editable=False)
    date_modification = models.DateTimeField(auto_now=True, editable=False)
    date_envoi_email = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        verbose_name = "Proforma"
        verbose_name_plural = "Proformas"
        ordering = ['-date_creation']
        unique_together = [('societe', 'numero')]
        db_table = 'facturer_devis'

    def __str__(self):
        return f"{self.numero or 'Nouveau'} — {self.client.nom if self.client else '(client manquant)'}"

    @property
    def display_numero(self):
        return self.numero if self.numero else "PROFORMA/—"

    def get_starting_sequence(self) -> int:
        return getattr(self.societe, 'numero_depart', 1) or 1

    def get_last_sequence(self) -> int:
        year = self.date_devis.year if self.date_devis else timezone.now().year
        candidats = Devis.objects.filter(
            societe=self.societe,
            date_devis__year=year,
            numero__isnull=False,
        ).exclude(numero='').exclude(pk=self.pk).values_list('numero', flat=True)
        max_seq = self.get_starting_sequence() - 1
        for numero in candidats:
            try:
                parts = numero.split('/')
                if len(parts) >= 2:
                    seq = int(parts[1])
                    if seq > max_seq:
                        max_seq = seq
            except (ValueError, IndexError):
                continue
        return max_seq

    def generate_numero(self):
        if self.numero:
            return
        year = self.date_devis.year if self.date_devis else timezone.now().year
        last_seq = self.get_last_sequence()
        new_seq = last_seq + 1
        self.numero = f"PROFORMA/{new_seq}/{year}"

    def _generate_uuid(self):
        import uuid
        return uuid.uuid4().hex

    def save(self, *args, **kwargs):
        if not self.societe_id:
            raise ValueError("La société doit être définie avant sauvegarde.")
        with transaction.atomic():
            if not self.numero:
                self.generate_numero()
            if not self.uuid_public:
                self.uuid_public = self._generate_uuid()
            if not self.date_validite:
                self.date_validite = (self.date_devis + timedelta(days=30)) if self.date_devis else (timezone.now().date() + timedelta(days=30))
            super().save(*args, **kwargs)
        if self.pk and hasattr(self, 'lignes_devis') and self.lignes_devis.exists():
            self.recalculer_totaux()

    def recalculer_totaux(self):
        lignes = self.lignes_devis.all()
        total_ht = Decimal('0')
        total_tva = Decimal('0')
        total_ttc = Decimal('0')
        for ligne in lignes:
            total_ht += ligne.montant_ht
            total_tva += ligne.montant_tva
            total_ttc += ligne.montant_ttc
        Devis.objects.filter(pk=self.pk).update(
            total_ht=total_ht.quantize(Decimal('0.001'), rounding=ROUND_DOWN),
            total_tva=total_tva.quantize(Decimal('0.001'), rounding=ROUND_DOWN),
            total_ttc=total_ttc.quantize(Decimal('0.001'), rounding=ROUND_DOWN),
        )
        self.refresh_from_db(fields=['total_ht', 'total_tva', 'total_ttc'])

    @property
    def peut_etre_supprime(self):
        return self.statut in ('BROUILLON', 'EN_ATTENTE', 'REFUSE', 'EXPIRE')

    @property
    def peut_etre_transformee(self):
        return self.statut == 'VALIDE' and not self.est_expire

    @property
    def est_expire(self):
        if not self.date_validite:
            return False
        return self.date_validite < date.today()


class LigneDevis(models.Model):
    devis = models.ForeignKey(Devis, on_delete=models.CASCADE, related_name='lignes_devis')
    produit = models.ForeignKey(Produit, on_delete=models.PROTECT, null=True, blank=True)
    service = models.ForeignKey(Service, on_delete=models.PROTECT, null=True, blank=True)
    designation = models.CharField(max_length=250)
    quantite = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    prix_vente_tvac = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True,
        verbose_name="Prix de vente TVAC",
    )
    prix_unitaire_ht = models.DecimalField(
        max_digits=14, decimal_places=4, default=0, editable=False,
    )
    taux_tva = models.ForeignKey(
        'taux.TauxTVA', on_delete=models.PROTECT, null=True, blank=True,
        verbose_name="Taux TVA",
    )

    class Meta:
        ordering = ['id']
        db_table = 'facturer_lignedevis'

    def __str__(self):
        return f"{self.designation} (x{self.quantite})"

    def _get_taux_effectif(self):
        societe = self.devis.societe
        if not getattr(societe, 'assujeti_tva', False):
            return TauxTVA.objects.filter(societe=societe, valeur=Decimal('0.00')).first()
        if not self.devis.applique_tva:
            return TauxTVA.objects.filter(societe=societe, valeur=Decimal('0.00')).first()
        objet = self.produit or self.service
        if objet and hasattr(objet, 'taux_tva') and objet.taux_tva:
            return objet.taux_tva
        return TauxTVA.objects.filter(societe=societe, valeur=Decimal('0.00')).first()

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.prix_vente_tvac is None:
            raise ValidationError({"prix_vente_tvac": "Le prix de vente TVAC est obligatoire."})

    def save(self, *args, **kwargs):
        self.full_clean()
        self.taux_tva = self._get_taux_effectif()
        prix_tvac = self.prix_vente_tvac or Decimal('0.00')
        qte = self.quantite or Decimal('1')
        taux = self.taux_tva.valeur if self.taux_tva else Decimal('0.00')
        if taux == 0:
            montant_ht = (prix_tvac * qte).quantize(Decimal('0.001'), rounding=ROUND_DOWN)
            montant_tva = Decimal('0.000')
        else:
            montant_ht = (prix_tvac * qte / (Decimal('1') + taux / Decimal('100'))).quantize(Decimal('0.001'), rounding=ROUND_DOWN)
            montant_tva = (montant_ht * taux / Decimal('100')).quantize(Decimal('0.001'), rounding=ROUND_DOWN)
        montant_ttc = (montant_ht + montant_tva).quantize(Decimal('0.001'), rounding=ROUND_DOWN)
        self.prix_unitaire_ht = (montant_ht / qte if qte != 0 else Decimal('0.0000')).quantize(Decimal('0.0001'), rounding=ROUND_DOWN)
        self._montant_ht = montant_ht
        self._montant_tva = montant_tva
        self._montant_ttc = montant_ttc
        super().save(*args, **kwargs)

    @property
    def montant_ht(self):
        if hasattr(self, '_montant_ht'):
            return self._montant_ht
        return self._calculer_montant_ht()

    @property
    def montant_tva(self):
        if hasattr(self, '_montant_tva'):
            return self._montant_tva
        if not self.devis.applique_tva:
            return Decimal('0.000')
        taux = getattr(self.taux_tva, 'valeur', Decimal('0')) or Decimal('0')
        return (self.montant_ht * taux / Decimal('100')).quantize(Decimal('0.001'), rounding=ROUND_DOWN)

    @property
    def montant_ttc(self):
        if hasattr(self, '_montant_ttc'):
            return self._montant_ttc
        return (self.montant_ht + self.montant_tva).quantize(Decimal('0.001'), rounding=ROUND_DOWN)

    def _calculer_montant_ht(self):
        prix = self.prix_vente_tvac or Decimal('0')
        qte = self.quantite or Decimal('1')
        taux = getattr(self.taux_tva, 'valeur', Decimal('0')) or Decimal('0')
        if taux == 0:
            return (prix * qte).quantize(Decimal('0.001'), rounding=ROUND_DOWN)
        prix_ht = (prix / (Decimal('1') + taux / Decimal('100'))).quantize(Decimal('0.0001'), rounding=ROUND_DOWN)
        return (prix_ht * qte).quantize(Decimal('0.001'), rounding=ROUND_DOWN)

    @property
    def taux_tva_valeur(self):
        return self.taux_tva.valeur if self.taux_tva else 0

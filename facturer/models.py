from decimal import Decimal
from django.db import models, transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from societe.models import Societe
from clients.models import Client
from produits.models import Produit
from services.models import Service
from taux.models import TauxTVA


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
        ('EN_ATTENTE', 'En cours'),
        ('ENVOYE',     'Envoyé OBR'),
        ('ECHEC',      'Échec envoi'),
        ('ANNULE',     'Annulé OBR'),
    ]

    societe = models.ForeignKey(Societe, on_delete=models.CASCADE, related_name='factures', verbose_name="Société")
    numero = models.CharField(max_length=50, blank=True, editable=False, verbose_name="N° Facture")
    
    invoice_identifier = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        unique=True,
        verbose_name="Identifiant facture OBR"
    )

    date_facture = models.DateField(default=timezone.now, verbose_name="Date")
    heure_facture = models.TimeField(default=timezone.now, verbose_name="Heure")
    type_facture = models.CharField(max_length=5, choices=TYPE_CHOICES, default='FN', verbose_name="Type")

    facture_originale = models.ForeignKey(
        'self', on_delete=models.PROTECT, null=True, blank=True,
        related_name='avoirs_lies', verbose_name="Facture originale"
    )
    motif_avoir = models.CharField(max_length=150, blank=True, verbose_name="Motif de l'avoir")

    bon_commande = models.CharField(max_length=100, blank=True, null=True, verbose_name="Bon de commande")
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='factures', verbose_name="Client")

    devise = models.CharField(max_length=5, choices=DEVISE_CHOICES, default='BIF', verbose_name="Devise")
    mode_paiement = models.CharField(max_length=10, choices=MODE_PAIEMENT_CHOICES, default='CAISSE', verbose_name="Mode de paiement")
    applique_tva = models.BooleanField(default=True, verbose_name="Appliquer la TVA")

    total_ht = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)
    total_tva = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)
    total_ttc = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)

    statut_obr = models.CharField(max_length=20, choices=STATUT_OBR_CHOICES, default='EN_ATTENTE', editable=False)
    message_obr = models.TextField(blank=True, editable=False)
    date_envoi_obr = models.DateTimeField(null=True, blank=True, editable=False)
    obr_registered_number = models.CharField(max_length=50, blank=True, null=True, editable=False)
    obr_registered_date = models.DateTimeField(null=True, blank=True, editable=False)
    electronic_signature = models.TextField(blank=True, editable=False)
    qr_code_image = models.ImageField(upload_to='qrcodes/factures/', blank=True, null=True)

    cree_par = models.ForeignKey('superadmin.Utilisateur', on_delete=models.SET_NULL, null=True,
                                 related_name='factures_creees', verbose_name="Créée par", editable=False)
    date_creation = models.DateTimeField(auto_now_add=True, editable=False)
    date_annulation = models.DateTimeField(null=True, blank=True)

    date_expiration = models.DateTimeField(null=True, blank=True)
    est_abandonnee = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Facture"
        verbose_name_plural = "Factures"
        ordering = ['-date_creation']
        unique_together = [('societe', 'numero')]

    def __str__(self):
        return f"{self.numero or 'Nouvelle'} — {self.client.nom if self.client else '(client manquant)'}"

    @property
    def display_numero(self):
        return self.numero if self.numero else f"{self.type_facture}/—"

    @property
    def numero_obr(self):
        if not self.numero:
            raise ValueError(f"La facture pk={self.pk} n'a pas encore de numéro.")
        return self.numero

    # ====================== GÉNÉRATION NUMÉRO ======================
    def get_starting_sequence(self) -> int:
        return getattr(self.societe, 'numero_depart', 1) or 1

    def get_last_sequence(self) -> int:
        year = self.date_facture.year if self.date_facture else timezone.now().year

        candidats = Facture.objects.filter(
            societe=self.societe,
            type_facture=self.type_facture,
            date_facture__year=year,
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
        year = self.date_facture.year if self.date_facture else timezone.now().year
        last_seq = self.get_last_sequence()
        new_seq = last_seq + 1
        self.numero = f"{self.type_facture}/{new_seq}/{year}"

    # ====================== GÉNÉRATION IDENTIFIER OBR ======================
    def generate_invoice_identifier(self):
        """Version finale selon ton souhait"""
        if not self.societe:
            raise ValueError("Société requise")

        system_id = (getattr(self.societe, "obr_system_id", "") or "").strip()
        company_nif = (getattr(self.societe, "nif", "") or "").strip()

        if not system_id or not company_nif:
            raise ValueError("NIF ou System ID manquant")

        now = timezone.now()
        datetime_str = now.strftime("%Y%m%d%H%M%S")

        # On met le vrai numéro complet (FN/62/2026)
        self.invoice_identifier = f"{company_nif}/{system_id}/{datetime_str}/{self.numero_obr}"
        return self.invoice_identifier

    # ====================== SAVE ======================
    def save(self, *args, **kwargs):
        if not self.societe_id:
            raise ValueError("La société doit être définie avant sauvegarde.")

        with transaction.atomic():
            if not self.numero:
                self.generate_numero()

            # Générer l'identifiant OBR systématiquement (important !)
            if not self.invoice_identifier:
                self.generate_invoice_identifier()

            # Date d'expiration
            if self.statut_obr == 'EN_ATTENTE' and not self.date_expiration:
                self.date_expiration = timezone.now() + timezone.timedelta(hours=2)

            super().save(*args, **kwargs)

        # Recalcul des totaux
        if self.pk and hasattr(self, 'lignes') and self.lignes.exists():
            self.recalculer_totaux()

    # ------------------------------------------------------------------ #
    #  NETTOYAGE AUTOMATIQUE des factures sans numéro (tâche périodique)  #
    # ------------------------------------------------------------------ #
    @classmethod
    def supprimer_factures_sans_numero(cls):
        """
        Supprime toutes les factures qui n'ont pas de numéro.
        À appeler depuis une tâche Celery/cron périodique, ou en signal
        post_migrate pour un nettoyage au démarrage.

        Ces enregistrements ne devraient jamais exister en production grâce
        au garde-fou dans save(), mais cette méthode sert de filet de sécurité
        en cas d'erreur passée ou de migration de données corrompues.

        Retourne le nombre de factures supprimées.
        """
        with transaction.atomic():
            qs = cls.objects.filter(numero='').select_for_update()
            count = qs.count()
            qs.delete()
        return count

    # ------------------------------------------------------------------ #
    #  CALCULS & UTILITAIRES                                              #
    # ------------------------------------------------------------------ #
    def recalculer_totaux(self):
        lignes = self.lignes.all()

        total_ht  = Decimal('0')
        total_tva = Decimal('0')
        total_ttc = Decimal('0')

        for ligne in lignes:
            total_ht  += ligne.montant_ht
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

    def nettoyer_mouvements_stock(self):
        """Nettoie les mouvements de stock EN_ATTENTE selon le type de facture."""
        from stock.models import SortieStock, EntreeStock

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


# ==================== LIGNE FACTURE ===================================== #
class LigneFacture(models.Model):
    facture = models.ForeignKey(Facture, on_delete=models.CASCADE, related_name='lignes')

    produit = models.ForeignKey(Produit, on_delete=models.PROTECT, null=True, blank=True)
    service = models.ForeignKey(Service, on_delete=models.PROTECT, null=True, blank=True)

    designation = models.CharField(max_length=250)
    quantite = models.DecimalField(max_digits=12, decimal_places=3, default=1)

    prix_vente_tvac = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Prix de vente TVAC",
    )

    prix_unitaire_ht = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        default=0,
        editable=False,
    )

    taux_tva = models.ForeignKey(
        'taux.TauxTVA',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Taux TVA",
    )

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.designation} (x{self.quantite})"

    # ------------------------------------------------------------------ #
    #  LOGIQUE TVA                                                         #
    # ------------------------------------------------------------------ #
    def _get_taux_effectif(self):
        """Retourne l'objet TauxTVA correct selon les règles métier."""
        societe = self.facture.societe

        # Règle Prioritaire : Société non assujettie à la TVA
        if not getattr(societe, 'assujeti_tva', False):
            return TauxTVA.objects.filter(
                societe=societe,
                valeur=Decimal('0.00'),
            ).first()

        # Si la facture elle-même ne veut pas appliquer la TVA
        if not self.facture.applique_tva:
            return TauxTVA.objects.filter(
                societe=societe,
                valeur=Decimal('0.00'),
            ).first()

        # Priorité au taux défini sur le Produit ou le Service
        objet = self.produit or self.service
        if objet and hasattr(objet, 'taux_tva') and objet.taux_tva:
            return objet.taux_tva

        # Fallback : 0% si rien n'est trouvé
        return TauxTVA.objects.filter(
            societe=societe,
            valeur=Decimal('0.00'),
        ).first()

    def clean(self):
        if self.prix_vente_tvac is None:
            raise ValidationError({"prix_vente_tvac": "Le prix de vente TVAC est obligatoire."})

    def save(self, *args, **kwargs):
        self.full_clean()

        self.taux_tva = self._get_taux_effectif()

        prix_tvac = self.prix_vente_tvac or Decimal('0.00')
        qte       = self.quantite or Decimal('1')
        taux      = self.taux_tva.valeur if self.taux_tva else Decimal('0.00')

        if taux == 0:
            self.prix_unitaire_ht = prix_tvac.quantize(Decimal('0.0001'))
            montant_ht  = (prix_tvac * qte).quantize(Decimal('0.001'))
            montant_tva = Decimal('0')
        else:
            self.prix_unitaire_ht = (
                prix_tvac / (Decimal('1') + taux / Decimal('100'))
            ).quantize(Decimal('0.0001'))
            montant_ht  = (self.prix_unitaire_ht * qte).quantize(Decimal('0.001'))
            montant_tva = (montant_ht * taux / Decimal('100')).quantize(Decimal('0.001'))

        montant_ttc = (montant_ht + montant_tva).quantize(Decimal('0.001'))

        self._montant_ht  = montant_ht
        self._montant_tva = montant_tva
        self._montant_ttc = montant_ttc

        super().save(*args, **kwargs)

    # ------------------------------------------------------------------ #
    #  PROPRIÉTÉS SÉCURISÉES                                              #
    # ------------------------------------------------------------------ #
    @property
    def montant_ht(self):
        if hasattr(self, '_montant_ht'):
            return self._montant_ht
        return self._calculer_montant_ht()

    @property
    def montant_tva(self):
        if hasattr(self, '_montant_tva'):
            return self._montant_tva
        if not self.facture.applique_tva:
            return Decimal('0.000')
        taux = getattr(self.taux_tva, 'valeur', Decimal('0')) or Decimal('0')
        return (self.montant_ht * taux / Decimal('100')).quantize(Decimal('0.001'))

    @property
    def montant_ttc(self):
        if hasattr(self, '_montant_ttc'):
            return self._montant_ttc
        return (self.montant_ht + self.montant_tva).quantize(Decimal('0.001'))

    def _calculer_montant_ht(self):
        prix = self.prix_vente_tvac or Decimal('0')
        qte  = self.quantite or Decimal('1')
        taux = getattr(self.taux_tva, 'valeur', Decimal('0')) or Decimal('0')

        if taux == 0:
            return (prix * qte).quantize(Decimal('0.001'))
        prix_ht = (prix / (Decimal('1') + taux / Decimal('100'))).quantize(Decimal('0.0001'))
        return (prix_ht * qte).quantize(Decimal('0.001'))

    @property
    def taux_tva_valeur(self):
        return self.taux_tva.valeur if self.taux_tva else 0

    def nettoyer_mouvements_stock(self):
        """Nettoie les mouvements de stock EN_ATTENTE liés à cette ligne."""
        from stock.models import SortieStock, EntreeStock

        type_facture = self.facture.type_facture

        with transaction.atomic():
            if type_facture == 'FN':
                deleted = SortieStock.objects.filter(
                    facture=self.facture,
                    statut_obr='EN_ATTENTE',
                ).delete()[0]
                action = f"{deleted} sortie(s) supprimée(s)"

            elif type_facture == 'FA':
                deleted = EntreeStock.objects.filter(
                    facture=self.facture,
                    statut_obr='EN_ATTENTE',
                ).delete()[0]
                action = f"{deleted} entrée retour supprimée(s)"

            else:
                action = "Aucun mouvement stock concerné"

            return action


# ==================== FILE D'ATTENTE OBR ================================ #
class FacturePendingOBR(models.Model):
    facture      = models.ForeignKey(Facture, on_delete=models.CASCADE, related_name='pending_obr')
    payload      = models.JSONField(blank=True, null=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    statut       = models.CharField(max_length=50, default='EN_ATTENTE')
    message      = models.TextField(blank=True, null=True)
    retry_count  = models.PositiveIntegerField(default=0, verbose_name="Nombre de tentatives")

    class Meta:
        verbose_name = "Facture en attente OBR"
        verbose_name_plural = "Factures en attente OBR"

    def __str__(self):
        return f"Pending OBR — {self.facture.display_numero} ({self.statut})"

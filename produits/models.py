from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Sum, Value
from django.db.models.functions import Coalesce
from decimal import Decimal

from societe.models import Societe
from categories.models import Categorie
from taux.models import Taux


class Produit(models.Model):
    ORIGINE_CHOICES = [
        ('LOCAL',   'Produit Local'),
        ('IMPORTE', 'Produit Importé'),
    ]

    STATUT_CHOICES = [
        ('ACTIF',     'Actif'),
        ('INACTIF',   'Inactif'),
        ('BROUILLON', 'Brouillon'),
    ]

    DEVISE_CHOICES = [
        ('BIF',  'BIF — Franc Burundais'),
        ('USD',  'USD — Dollar Américain'),
        ('EUR',  'EUR — Euro'),
    ]

    societe     = models.ForeignKey(
        Societe,
        on_delete=models.CASCADE,
        related_name='produits',
        verbose_name="Société"
    )
    categorie   = models.ForeignKey(
        Categorie,
        on_delete=models.CASCADE,
        related_name='produits',
        verbose_name="Catégorie"
    )
    code        = models.CharField(
        max_length=50,
        verbose_name="Code produit",
        help_text="Code interne unique à la société (ex: PROD-001)"
    )
    designation = models.CharField(
        max_length=200,
        verbose_name="Désignation",
        help_text="Nom complet du produit"
    )
    unite       = models.CharField(
        max_length=50,
        verbose_name="Unité de mesure",
        help_text="Ex: kg, litre, pièce, carton"
    )
    prix_vente  = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Prix de vente unitaire HT",
        help_text="Prix de vente hors taxes (HTVA)"
    )
    devise      = models.CharField(
        max_length=10,
        choices=DEVISE_CHOICES,
        default='BIF',
        verbose_name="Devise"
    )
    taux_tva    = models.ForeignKey(
        Taux,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='produits',
        verbose_name="Taux TVA"
    )
    origine = models.CharField(
        max_length=10,
        choices=ORIGINE_CHOICES,
        default='LOCAL',
        verbose_name="Origine"
    )
    statut      = models.CharField(
        max_length=20,
        choices=STATUT_CHOICES,
        default='ACTIF',
        verbose_name="Statut"
    )

    # ─── Champs spécifiques OBR (importés) ────────────────────────────────────────
    reference_dmc = models.CharField(
        max_length=100,
        blank=True,
        default='',
        verbose_name="Référence DMC",
        help_text="Référence de la déclaration de mise en consommation (OBR)"
    )
    rubrique_tarifaire = models.CharField(
        max_length=50,
        blank=True,
        default='',
        verbose_name="Rubrique tarifaire",
        help_text="Code du tarif douanier (ex: 15119090000)"
    )
    nombre_par_paquet = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Nombre par paquet",
        help_text="Nombre de pièces/unité par conditionnement"
    )
    description_paquet = models.CharField(
        max_length=150,
        blank=True,
        default='',
        verbose_name="Description conditionnement",
        help_text="Ex: carton de 12, sachet de 500g, boîte"
    )

    # Champs de traçabilité
    date_creation     = models.DateTimeField(
        default=timezone.now,
        editable=False,
        verbose_name="Créé le"
    )
    date_modification = models.DateTimeField(
        auto_now=True,
        verbose_name="Modifié le"
    )

    class Meta:
        verbose_name        = "Produit"
        verbose_name_plural = "Produits"
        ordering            = ['code', 'designation']
        unique_together     = [('societe', 'code')]
        indexes = [
            models.Index(fields=['societe', 'code']),
            models.Index(fields=['societe', 'origine']),
            models.Index(fields=['reference_dmc']),
        ]

    def __str__(self):
        return f"{self.designation} ({self.code})"

    @property
    def est_importe(self):
        return self.origine == 'IMPORTE'

    @property
    def infos_obr_completes(self):
        """Vérifie si les informations OBR obligatoires sont présentes"""
        if not self.est_importe:
            return True
        return all([
            bool(self.reference_dmc and str(self.reference_dmc).strip()),
            bool(self.rubrique_tarifaire and str(self.rubrique_tarifaire).strip()),
            self.nombre_par_paquet is not None and self.nombre_par_paquet > 0,
            bool(self.description_paquet and str(self.description_paquet).strip()),
        ])

    @property
    def taux_tva_valeur(self):
        """Retourne le taux TVA en % (18 par défaut si null)"""
        return float(self.taux_tva.valeur if self.taux_tva else 18)

    @property
    def prix_vente_tvac(self):
        """Prix de vente TTC calculé"""
        tva_rate = Decimal(str(self.taux_tva_valeur)) / Decimal('100')
        prix_ht = Decimal(str(self.prix_vente or 0))
        return float((prix_ht * (Decimal('1') + tva_rate)).quantize(Decimal('0.01')))

    @property
    def tva_montant(self):
        """Montant de la TVA unitaire"""
        return float(Decimal(str(self.prix_vente_tvac)) - Decimal(str(self.prix_vente or 0)))

    def clean(self):
        if self.prix_vente < 0:
            raise ValidationError("Le prix de vente ne peut pas être négatif.")

        # Validation renforcée pour les produits importés
        if self.est_importe:
            missing = []

            if not self.reference_dmc or not str(self.reference_dmc).strip():
                missing.append("Référence DMC")

            if not self.rubrique_tarifaire or not str(self.rubrique_tarifaire).strip():
                missing.append("Rubrique tarifaire")

            # Correction importante : on accepte seulement si > 0
            if self.nombre_par_paquet is None or self.nombre_par_paquet <= 0:
                missing.append("Nombre par paquet (> 0)")

            if not self.description_paquet or not str(self.description_paquet).strip():
                missing.append("Description conditionnement")

            if missing:
                raise ValidationError(
                    f"Pour un produit importé, les champs suivants sont obligatoires : {', '.join(missing)}"
                )

    def save(self, *args, **kwargs):
        self.full_clean()   # Déclenche la validation
        super().save(*args, **kwargs)

    # ===================================================================
    #  GESTION DU STOCK (inchangée)
    # ===================================================================

    @property
    def stock_disponible(self) -> Decimal:
        from decimal import Decimal
        from django.db.models import Sum, Value
        from django.db.models.functions import Coalesce
        from stock.models import EntreeStock, SortieStock

        statuts_confirmes = ['ENVOYE', 'VALIDE']

        total_entrees = EntreeStock.objects.filter(
            produit=self,
            societe=self.societe,
            statut_obr__in=statuts_confirmes
        ).aggregate(
            total=Coalesce(Sum('quantite'), Value(Decimal('0')))
        )['total']

        total_sorties = SortieStock.objects.filter(
            entree_stock__produit=self,
            entree_stock__societe=self.societe,
            statut_obr__in=statuts_confirmes
        ).aggregate(
            total=Coalesce(Sum('quantite'), Value(Decimal('0')))
        )['total']

        disponible = total_entrees - total_sorties
        return max(disponible, Decimal('0'))

    def ajuster_stock(self, quantite: Decimal, type_facture: str, facture=None):
        from decimal import Decimal
        from django.db import transaction
        from django.utils import timezone
        from stock.models import SortieStock, EntreeStock
        import logging
        import uuid

        logger = logging.getLogger(__name__)

        quantite = Decimal(str(quantite))
        if quantite <= 0:
            raise ValueError("La quantité doit être positive")

        type_facture = type_facture.upper().strip()

        facture_numero = getattr(facture, 'numero', None) or f"FACT-{getattr(facture, 'pk', 'NEW')}"
        client_nom = facture.client.nom if facture and hasattr(facture, 'client') and facture.client else ""

        with transaction.atomic():
            if type_facture == 'FN':
                entree = self.entrees_stock.filter(societe=self.societe).first()
                if not entree:
                    raise ValueError(f"Aucune entrée de stock trouvée pour le produit {self.designation}")

                unique_suffix = str(uuid.uuid4())[:8]

                SortieStock.objects.create(
                    societe=self.societe,
                    type_sortie='SN',
                    entree_stock=entree,
                    quantite=quantite,
                    prix=Decimal(str(self.prix_vente_tvac or 0)),
                    date_sortie=timezone.now().date(),
                    code=f"SORT-{self.code}-{unique_suffix}",
                    commentaire=f"Vente via facture {facture_numero}",
                    statut_obr='EN_ATTENTE',
                    facture=facture,
                )
                logger.info(f"[Stock] Sortie SN créée pour facture FN {facture_numero} - Qté: {quantite}")

            elif type_facture == 'FA':
                if not facture or not facture.facture_originale:
                    raise ValueError("Une facture d'avoir (FA) doit être liée à une facture originale (FN).")

                ligne_originale = facture.facture_originale.lignes.filter(produit=self).first()
                if not ligne_originale:
                    raise ValueError(f"Aucune ligne trouvée pour ce produit dans la facture originale.")

                quantite_max_autorisee = ligne_originale.quantite

                if quantite > quantite_max_autorisee:
                    raise ValueError(f"Quantité d'avoir ({quantite}) dépasse la quantité vendue sur la FN de référence.")

                entree, created = EntreeStock.objects.get_or_create(
                    societe=self.societe,
                    produit=self,
                    facture=facture,
                    type_entree='ER',
                    defaults={
                        'date_entree': timezone.now().date(),
                        'quantite': quantite,
                        'prix_revient': Decimal(str(self.prix_vente or 0)),
                        'prix_vente_actuel': Decimal(str(self.prix_vente_tvac or 0)),
                        'numero_ref': f"RET-ER-{facture_numero}",
                        'commentaire': f"Retour client via avoir {facture_numero} - {client_nom}",
                        'statut_obr': 'EN_ATTENTE',
                        'fournisseur': None,
                    }
                )

                if not created:
                    entree.quantite += quantite
                    entree.save(update_fields=['quantite', 'date_modification'])

            else:
                raise ValueError(f"Type de facture non supporté : {type_facture}")

            self.refresh_from_db()
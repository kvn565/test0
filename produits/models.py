# produits/models.py — VERSION CORRIGÉE
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
from django.db.models import Max, Sum, Value
from django.db.models.functions import Coalesce

from django.db import transaction
from django.db.models.functions import Cast, Substr

from societe.models import Societe
from categories.models import Categorie
from taux.models import TauxTVA


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
        ('BIF', 'BIF — Franc Burundais'),
        ('USD', 'USD — Dollar Américain'),
        ('EUR', 'EUR — Euro'),
    ]

    societe   = models.ForeignKey(Societe,   on_delete=models.CASCADE, related_name='produits',  verbose_name="Société")
    categorie = models.ForeignKey(Categorie, on_delete=models.CASCADE, related_name='produits',  verbose_name="Catégorie")

    # ✅ CORRECTION 1 : pas de unique=True global — unicité uniquement via unique_together (par société)
    # unique=True global empêchait deux sociétés différentes d'avoir le même code DMC → faux métier
    code = models.CharField(
        max_length=50,
        verbose_name="Code produit",
        help_text="Code interne unique à la société"
    )

    designation = models.CharField(max_length=200, verbose_name="Désignation")
    unite       = models.CharField(max_length=50,  verbose_name="Unité de mesure")
    prix_vente  = models.DecimalField(max_digits=12, decimal_places=3, verbose_name="Prix de vente unitaire HT")
    devise      = models.CharField(max_length=10, choices=DEVISE_CHOICES, default='BIF')

    # ✅ CORRECTION 2 : SET_NULL au lieu de PROTECT
    # PROTECT plantait toute l'appli si un admin supprimait un taux TVA utilisé
    taux_tva = models.ForeignKey(
        TauxTVA,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='produits',
        verbose_name="Taux TVA"
    )

    origine = models.CharField(max_length=10, choices=ORIGINE_CHOICES, default='LOCAL')
    statut  = models.CharField(max_length=20, choices=STATUT_CHOICES,  default='ACTIF')

    # Champs OBR
    reference_dmc      = models.CharField(max_length=100, blank=True, default='', verbose_name="Référence DMC")
    rubrique_tarifaire = models.CharField(max_length=50,  blank=True, default='', verbose_name="Rubrique tarifaire")
    nombre_par_paquet  = models.PositiveIntegerField(null=True, blank=True, verbose_name="Nombre par paquet")
    description_paquet = models.CharField(max_length=150, blank=True, default='', verbose_name="Description conditionnement")

    date_creation     = models.DateTimeField(default=timezone.now, editable=False)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Produit"
        verbose_name_plural = "Produits"
        ordering            = ['code']
        unique_together     = [('societe', 'code')]   # ✅ unicité par société uniquement
        indexes = [
            models.Index(fields=['societe', 'code']),
            models.Index(fields=['societe', 'origine']),
            models.Index(fields=['reference_dmc']),
        ]

    def __str__(self):
        return f"{self.designation} ({self.code})"

    # ── Génération automatique du code LOCAL ─────────────────────────────────

        # ── Génération automatique du code LOCAL ─────────────────────────────────
    def _generer_code_local(self):
        """
        Génère ATX1, ATX2, ATX3... de façon fiable et atomique
        """
        prefix = "ATX"
        
        # Verrouillage pour éviter les doublons en cas de création simultanée
        with transaction.atomic():
            # Récupérer le plus grand numéro existant
            dernier_code = (
                Produit.objects
                .filter(
                    societe=self.societe,
                    origine='LOCAL',
                    code__startswith=prefix
                )
                .annotate(
                    num=models.functions.Cast(
                        models.functions.Substr('code', len(prefix) + 1), 
                        output_field=models.IntegerField()
                    )
                )
                .aggregate(max_num=Max('num'))['max_num']
            )

            prochain_numero = (dernier_code or 0) + 1
            nouveau_code = f"{prefix}{prochain_numero}"

            # Vérification finale (sécurité)
            if Produit.objects.filter(societe=self.societe, code=nouveau_code).exists():
                # En cas de collision très rare, on recommence
                return self._generer_code_local()

            return nouveau_code

    # ── Validation ───────────────────────────────────────────────────────────

    def clean(self):
        if self.prix_vente is not None and self.prix_vente < 0:
            raise ValidationError("Le prix de vente ne peut pas être négatif.")

        # Protection code ATX sur produit importé
        if self.origine == 'IMPORTE' and self.code and str(self.code).upper().startswith('ATX'):
            raise ValidationError("Les produits importés ne peuvent pas utiliser un code commençant par ATX.")

        # Validation OBR
        if self.origine == 'IMPORTE':
            missing = []
            if not self.reference_dmc or not str(self.reference_dmc).strip():
                missing.append("Référence DMC")
            if not self.rubrique_tarifaire or not str(self.rubrique_tarifaire).strip():
                missing.append("Rubrique tarifaire")
            if self.nombre_par_paquet is None or self.nombre_par_paquet <= 0:
                missing.append("Nombre par paquet (> 0)")
            if not self.description_paquet or not str(self.description_paquet).strip():
                missing.append("Description conditionnement")
            if missing:
                raise ValidationError(
                    f"Pour un produit importé, les champs suivants sont obligatoires : {', '.join(missing)}"
                )

    def save(self, *args, **kwargs):
        # Générer le code uniquement pour les produits LOCAUX sans code
        if (self.origine == 'LOCAL' and 
            (not self.code or not str(self.code).strip())):
            
            if self.societe_id:  # Sécurité : societe doit être définie
                self.code = self._generer_code_local()

        self.full_clean()   # Lance les validations
        super().save(*args, **kwargs)

    # ── Propriétés ───────────────────────────────────────────────────────────

    @property
    def est_importe(self):
        return self.origine == 'IMPORTE'

    @property
    def taux_tva_valeur(self) -> Decimal:
        """Retourne 0 si la société n'est PAS assujettie à la TVA"""
        if not getattr(self.societe, 'assujeti_tva', False):
            return Decimal('0.00')          # Forcé à 0
        
        # Si la société est assujettie
        if self.taux_tva:
            return self.taux_tva.valeur
        return Decimal('0.00')


    @property
    def tva_montant(self) -> Decimal:
        """Calcul de la TVA sans arrondissement (3 décimales)"""
        if not self.prix_vente or self.taux_tva_valeur == 0:
            return Decimal('0.000')
        
        montant = (self.prix_vente * self.taux_tva_valeur / Decimal('100'))
        return montant.quantize(Decimal('0.001'), rounding='ROUND_DOWN')


    @property
    def prix_vente_tvac(self) -> Decimal:
        """Prix TVAC avec 3 décimales sans arrondissement"""
        if not self.prix_vente:
            return Decimal('0.000')
        
        tvac = self.prix_vente + self.tva_montant
        return tvac.quantize(Decimal('0.001'), rounding='ROUND_DOWN')

    @property
    def infos_obr_completes(self):
        if not self.est_importe:
            return True
        return all([
            bool(self.reference_dmc      and str(self.reference_dmc).strip()),
            bool(self.rubrique_tarifaire and str(self.rubrique_tarifaire).strip()),
            self.nombre_par_paquet is not None and self.nombre_par_paquet > 0,
            bool(self.description_paquet and str(self.description_paquet).strip()),
        ])

    # ====================== GESTION DU STOCK ======================

    @property
    def stock_disponible(self) -> Decimal:
        """Stock réellement disponible (seuls les mouvements confirmés OBR)"""
        from stock.models import EntreeStock, SortieStock

        statuts_valides = ['ENVOYE', 'NON_CONCERNE']

        total_entrees = EntreeStock.objects.filter(
            produit=self,
            societe=self.societe,
            statut_obr__in=statuts_valides
        ).aggregate(total=Coalesce(Sum('quantite'), Value(Decimal('0'))))['total']

        total_sorties = SortieStock.objects.filter(
            entree_stock__produit=self,
            entree_stock__societe=self.societe,
            statut_obr__in=statuts_valides
        ).aggregate(total=Coalesce(Sum('quantite'), Value(Decimal('0'))))['total']

        disponible = (total_entrees or Decimal('0')) - (total_sorties or Decimal('0'))
        return max(disponible, Decimal('0'))

    @property
    def stock_en_attente(self) -> Decimal:
        """Quantité bloquée en attente d'envoi à l'OBR"""
        from stock.models import EntreeStock, SortieStock

        total_entrees_attente = EntreeStock.objects.filter(
            produit=self, societe=self.societe, statut_obr='EN_ATTENTE'
        ).aggregate(total=Coalesce(Sum('quantite'), Value(Decimal('0'))))['total']

        total_sorties_attente = SortieStock.objects.filter(
            entree_stock__produit=self, entree_stock__societe=self.societe, statut_obr='EN_ATTENTE'
        ).aggregate(total=Coalesce(Sum('quantite'), Value(Decimal('0'))))['total']

        return (total_entrees_attente or Decimal('0')) - (total_sorties_attente or Decimal('0'))

    @property
    def stock_projete(self) -> Decimal:
        """
        Stock visible en temps réel pendant la saisie.
        = stock confirmé (ENVOYE) - lignes FN EN_ATTENTE + lignes FA EN_ATTENTE
        Ne dépend PAS des mouvements SortieStock/EntreeStock (créés seulement après OBR).
        """
        from django.db.models import Sum, Value
        from django.db.models.functions import Coalesce

        # Import local pour éviter les imports circulaires
        from facturer.models import LigneFacture

        sorties_prevues = LigneFacture.objects.filter(
            produit=self,
            facture__societe=self.societe,
            facture__type_facture='FN',
            facture__statut_obr='EN_ATTENTE',
        ).aggregate(total=Coalesce(Sum('quantite'), Value(Decimal('0'))))['total'] or Decimal('0')

        retours_prevus = LigneFacture.objects.filter(
            produit=self,
            facture__societe=self.societe,
            facture__type_facture='FA',
            facture__statut_obr='EN_ATTENTE',
        ).aggregate(total=Coalesce(Sum('quantite'), Value(Decimal('0'))))['total'] or Decimal('0')

        projete = self.stock_disponible - sorties_prevues + retours_prevus
        return max(projete, Decimal('0'))


    def ajuster_stock(self, quantite: Decimal, type_facture: str, facture=None):
        """Créer une sortie (FN) ou une entrée retour (FA)"""
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
        client_nom = getattr(getattr(facture, 'client', None), 'nom', '') if facture else ""

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

                if quantite > ligne_originale.quantite:
                    raise ValueError(f"Quantité d'avoir ({quantite}) dépasse la quantité vendue sur la FN.")

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

    def nettoyer_mouvements_facture(self, facture):
        """
        Supprime les mouvements de stock EN_ATTENTE liés à une facture annulée ou quittée.
        À appeler lorsque tu annules une facture.
        """
        from stock.models import EntreeStock, SortieStock
        from django.db import transaction

        with transaction.atomic():
            entrees_deleted = EntreeStock.objects.filter(
                facture=facture,
                statut_obr='EN_ATTENTE'
            ).delete()[0]

            sorties_deleted = SortieStock.objects.filter(
                facture=facture,
                statut_obr='EN_ATTENTE'
            ).delete()[0]

            total = entrees_deleted + sorties_deleted

            if total > 0:
                print(f"[STOCK NETTOYAGE] Facture {facture} → {entrees_deleted} entrée(s) + "
                      f"{sorties_deleted} sortie(s) supprimées (EN_ATTENTE)")

            return total

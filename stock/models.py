from django.db import models
from django.db.models import Sum
from decimal import Decimal

from societe.models import Societe
from produits.models import Produit
from fournisseurs.models import Fournisseur


class EntreeStock(models.Model):

    TYPE_ENTREE_CHOICES = [
        ('EN',  'EN – Entrée Normale'),
        ('ER',  'ER – Entrée Retour'),
        ('EI',  'EI – Entrée Inventaire'),
        ('EAJ', 'EAJ – Entrée Ajustement'),
        ('ET',  'ET – Entrée Transfert'),
        ('EA',  'EA – Entrée Autres'),
    ]

    STATUT_OBR_CHOICES = [
        ('EN_ATTENTE',   'En attente'),
        ('ENVOYE',       'Envoyé OBR'),
        ('ECHEC',        'Échec envoi'),
        ('NON_CONCERNE', 'Non concerné'),
    ]

    societe           = models.ForeignKey(Societe, on_delete=models.CASCADE, related_name='entrees_stock')
    type_entree       = models.CharField(max_length=5, choices=TYPE_ENTREE_CHOICES, verbose_name="Type d'entrée")
    numero_ref        = models.CharField(max_length=50, blank=True, verbose_name="N° Référence")
    date_entree       = models.DateField(verbose_name="Date d'entrée")

    produit           = models.ForeignKey(Produit, on_delete=models.PROTECT, related_name='entrees_stock', verbose_name="Produit")
    fournisseur       = models.ForeignKey(Fournisseur, on_delete=models.SET_NULL, null=True, blank=True, related_name='entrees_stock')

    quantite          = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Quantité")
    prix_revient      = models.DecimalField(max_digits=12, decimal_places=3, verbose_name="Prix de revient")
    prix_vente_actuel = models.DecimalField(max_digits=12, decimal_places=3, verbose_name="Prix de vente actuel (TVAC)")

    commentaire       = models.TextField(blank=True, null=True, verbose_name="Commentaire")
    facture           = models.ForeignKey(
        'facturer.Facture',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='entrees_stock',
        verbose_name="Facture liée"
    )

    statut_obr     = models.CharField(max_length=20, choices=STATUT_OBR_CHOICES, default='EN_ATTENTE')
    message_obr    = models.TextField(blank=True)
    date_envoi_obr = models.DateTimeField(null=True, blank=True)

    date_creation     = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Entrée stock"
        verbose_name_plural = "Entrées stock"
        ordering            = ['-date_creation']
        unique_together     = [('societe', 'produit', 'facture', 'type_entree')]
        indexes = [
            models.Index(fields=['societe', 'produit', 'date_entree']),
            models.Index(fields=['statut_obr']),
            models.Index(fields=['facture']),
        ]

    def __str__(self):
        return f"{self.type_entree} | {self.produit.designation} | {self.quantite}"

    def save(self, *args, **kwargs):
        # ====================== CORRECTION PRINCIPALE ======================
        if self.produit_id:
            # On ne met le prix_vente_actuel automatiquement QUE s'il est vide
            if not self.prix_vente_actuel or self.prix_vente_actuel == 0:
                self.prix_vente_actuel = self.produit.prix_vente_tvac

            # On NE force PLUS l'égalité prix_revient == prix_vente_actuel
            # Même si la société n'est pas assujettie à la TVA
            # L'utilisateur doit pouvoir saisir les deux valeurs librement

        super().save(*args, **kwargs)

    # ── Propriétés ──────────────────────────────────────────────────────

    @property
    def montant_total(self) -> Decimal:
        return self.quantite * self.prix_revient

    @property
    def quantite_sortie(self) -> Decimal:
        from .models import SortieStock   # Import local pour éviter circularité
        return SortieStock.objects.filter(entree_stock=self).aggregate(
            total=Sum('quantite')
        )['total'] or Decimal('0')

    @property
    def quantite_disponible(self) -> Decimal:
        return self.quantite - self.quantite_sortie

    @property
    def type_produit(self) -> str:
        return getattr(self.produit, 'origine', '—')


# ═══════════════════════════════════════════════════════════════════════
class SortieStock(models.Model):

    TYPE_SORTIE_CHOICES = [
        ('SN',  'SN – Sortie Normale (Vente)'),
        ('SP',  'SP – Sortie Perte'),
        ('SV',  'SV – Sortie Vol'),
        ('SD',  'SD – Sortie Désuétude'),
        ('SC',  'SC – Sortie Casse'),
        ('SAJ', 'SAJ – Sortie Ajustement'),
        ('ST',  'ST – Sortie Transfert'),
        ('SAU', 'SAU – Sortie Autres'),
    ]

    STATUT_OBR_CHOICES = [
        ('EN_ATTENTE',   'En attente'),
        ('ENVOYE',       'Envoyé OBR'),
        ('ECHEC',        'Échec envoi'),
        ('NON_CONCERNE', 'Non concerné'),
    ]

    societe      = models.ForeignKey(Societe, on_delete=models.CASCADE, related_name='sorties_stock')
    type_sortie  = models.CharField(max_length=5, choices=TYPE_SORTIE_CHOICES, verbose_name="Type de sortie")
    code         = models.CharField(max_length=50, blank=True, verbose_name="Code sortie")
    date_sortie  = models.DateField(verbose_name="Date de sortie")

    entree_stock = models.ForeignKey(
        EntreeStock,
        on_delete=models.PROTECT,
        related_name='sorties',
        verbose_name="Produit (depuis stock)"
    )

    quantite     = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Quantité sortie")
    prix         = models.DecimalField(max_digits=12, decimal_places=3, verbose_name="Prix unitaire (TVAC)")

    commentaire  = models.TextField(blank=True, verbose_name="Commentaire")
    facture      = models.ForeignKey(
        'facturer.Facture',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='sorties_stock'
    )

    statut_obr     = models.CharField(max_length=20, choices=STATUT_OBR_CHOICES, default='EN_ATTENTE')
    message_obr    = models.TextField(blank=True)
    date_envoi_obr = models.DateTimeField(null=True, blank=True)

    date_creation     = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Sortie stock"
        verbose_name_plural = "Sorties stock"
        ordering            = ['-date_creation']

    def __str__(self):
        try:
            designation = self.entree_stock.produit.designation
        except Exception:
            designation = '—'
        return f"{self.type_sortie} | {designation} | {self.quantite}"

    def save(self, *args, **kwargs):
        if self.entree_stock_id:
            # On prend le prix de vente actuel de l'entrée (priorité)
            if not self.prix:
                self.prix = self.entree_stock.prix_vente_actuel or self.entree_stock.produit.prix_vente_tvac

        super().save(*args, **kwargs)

    # ── Propriétés ──────────────────────────────────────────────────────

    @property
    def produit(self) -> Produit:
        return self.entree_stock.produit

    @property
    def montant_total(self) -> Decimal:
        return self.quantite * self.prix

    @property
    def quantite_en_stock(self) -> Decimal:
        from .models import SortieStock
        total_sorti = SortieStock.objects.filter(
            entree_stock=self.entree_stock
        ).exclude(pk=self.pk).aggregate(
            total=Sum('quantite')
        )['total'] or Decimal('0')
        return self.entree_stock.quantite - total_sorti
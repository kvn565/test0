from django.db import models
from django.db.models import Sum
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
    numero_ref        = models.CharField(max_length=50, blank=True, verbose_name="N° Réquisition / Réf. fiche")
    date_entree       = models.DateField(verbose_name="Date d'entrée")
    produit           = models.ForeignKey(Produit, on_delete=models.PROTECT, related_name='entrees_stock', verbose_name="Produit")
    fournisseur       = models.ForeignKey(Fournisseur, on_delete=models.SET_NULL, null=True, blank=True, related_name='entrees_stock', verbose_name="Fournisseur")
    quantite          = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Quantité")
    prix_revient      = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Prix de revient")
    prix_vente_actuel = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Prix de vente actuel")
    statut_obr        = models.CharField(max_length=20, choices=STATUT_OBR_CHOICES, default='EN_ATTENTE', verbose_name="Statut OBR")
    message_obr       = models.TextField(blank=True, verbose_name="Message OBR")
    date_envoi_obr    = models.DateTimeField(null=True, blank=True)
    date_creation     = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    # === NOUVEAUX CHAMPS AJOUTÉS ===
    commentaire       = models.TextField(blank=True, null=True, verbose_name="Commentaire")
    facture           = models.ForeignKey(
        'facturer.Facture', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='entrees_stock',
        verbose_name="Facture liée"
    )

    class Meta:
        verbose_name        = "Entrée stock"
        verbose_name_plural = "Entrées stock"
        ordering            = ['-date_creation']
        
        # ==================== CORRECTION PRINCIPALE ====================
        # Empêche les doublons d'entrées, surtout les retours (ER) liés à une facture
        unique_together = [
            ('societe', 'produit', 'facture', 'type_entree'),
        ]
        
        indexes = [
            models.Index(fields=['societe', 'produit', 'date_entree']),
            models.Index(fields=['statut_obr']),
            models.Index(fields=['facture']),           # Utile pour les liens avec FA
        ]

    def __str__(self):
        return f"{self.type_entree} | {self.produit.designation} | {self.quantite} | {self.date_entree}"

    @property
    def montant_total(self):
        return self.quantite * self.prix_revient

    @property
    def quantite_sortie(self):
        return SortieStock.objects.filter(
            entree_stock=self
        ).aggregate(total=Sum('quantite'))['total'] or 0

    @property
    def quantite_disponible(self):
        return self.quantite - self.quantite_sortie

    @property
    def type_produit(self):
        return self.produit.origine if hasattr(self.produit, 'origine') else '—'


# ══════════════════════════════════════════════════════════
#  SORTIE STOCK (hors vente)
# ══════════════════════════════════════════════════════════
class SortieStock(models.Model):

    TYPE_SORTIE_CHOICES = [
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

    societe           = models.ForeignKey(Societe, on_delete=models.CASCADE, related_name='sorties_stock')
    type_sortie       = models.CharField(max_length=5, choices=TYPE_SORTIE_CHOICES, verbose_name="Type de sortie")
    code              = models.CharField(max_length=50, blank=True, verbose_name="Code sortie")
    date_sortie       = models.DateField(verbose_name="Date de sortie")
    entree_stock      = models.ForeignKey(
        EntreeStock, on_delete=models.PROTECT,
        related_name='sorties',
        verbose_name="Produit (depuis stock)"
    )
    quantite          = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Quantité sortie")
    prix              = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Prix unitaire")
    commentaire       = models.TextField(blank=True, verbose_name="Commentaire / Explication")
    statut_obr        = models.CharField(max_length=20, choices=STATUT_OBR_CHOICES, default='EN_ATTENTE', verbose_name="Statut OBR")
    message_obr       = models.TextField(blank=True, verbose_name="Message OBR")
    date_envoi_obr    = models.DateTimeField(null=True, blank=True)
    date_creation     = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    facture = models.ForeignKey(
        'facturer.Facture', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='sorties_stock',
        verbose_name="Facture liée"
    )

    class Meta:
        verbose_name        = "Sortie stock"
        verbose_name_plural = "Sorties stock"
        ordering            = ['-date_creation']

    def __str__(self):
        return f"{self.type_sortie} | {self.entree_stock.produit.designation} | {self.quantite} | {self.date_sortie}"

    @property
    def produit(self):
        return self.entree_stock.produit

    @property
    def montant_total(self):
        return self.quantite * self.prix

    @property
    def quantite_en_stock(self):
        """Stock disponible = total entré - total sorti (hors cette sortie)"""
        total_sorti = SortieStock.objects.filter(
            entree_stock=self.entree_stock
        ).exclude(pk=self.pk).aggregate(
            total=models.Sum('quantite')
        )['total'] or 0
        return self.entree_stock.quantite - total_sorti
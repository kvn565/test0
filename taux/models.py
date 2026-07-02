from decimal import Decimal, ROUND_DOWN  
from decimal import Decimal
from django.db import models
from societe.models import Societe


class TauxTVAManager(models.Manager):
    def for_societe(self, societe):
        """Tous les taux de la société"""
        if not societe:
            return self.none()
        return self.filter(societe=societe).order_by('valeur')

    def for_formulaire(self, societe):
        """Pour le formulaire : montre tous les taux (important pour OBR)"""
        return self.for_societe(societe)

    def for_facture(self, societe):
        """Pour le module Facture : respecte la règle métier stricte"""
        if not societe:
            return self.none()
        if getattr(societe, 'assujeti_tva', False):
            return self.for_societe(societe)
        else:
            # Non assujetti → uniquement taux 0%
            return self.for_societe(societe).filter(valeur=Decimal('0.00'))

    def get_taux_defaut(self, societe):
        """Retourne le taux par défaut (est_defaut=True) ou le plus élevé"""
        if not societe:
            return None
        qs = self.for_societe(societe)
        return qs.filter(est_defaut=True).first() or qs.order_by('-valeur').first()

    def resolve_for_obr(self, societe):
        """
        Résout le taux TVA à utiliser pour l'import OBR.
        - Assujetti    → taux par défaut (est_defaut=True) ou le plus élevé (18% puis 10%)
        - Non assujetti → toujours 0%
        """
        if not societe:
            return None

        if not getattr(societe, 'assujeti_tva', False):
            # Non assujetti → 0%
            return self.for_societe(societe).filter(valeur=Decimal('0.00')).first()

        # Assujetti → on privilégie le taux par défaut, sinon le plus élevé
        taux = self.get_taux_defaut(societe)
        return taux or self.for_societe(societe).first()


class TauxTVA(models.Model):
    societe = models.ForeignKey(
        Societe,
        on_delete=models.CASCADE,
        related_name='taux_tva',
        verbose_name="Société"
    )

    nom = models.CharField(max_length=100, verbose_name="Nom du taux")
    
    valeur = models.DecimalField(
        max_digits=6,           # Augmenté pour supporter XXX.XXX
        decimal_places=3,       # ← Changement principal
        verbose_name="Taux (%)",
        help_text="Exemple : 18.000 pour 18%, 16.667 pour 16.667%, 5.500 pour 5.5%"
    )
    
    est_defaut = models.BooleanField(default=False, verbose_name="Taux par défaut")
    date_creation = models.DateTimeField(auto_now_add=True)

    objects = TauxTVAManager()

    class Meta:
        verbose_name = "Taux TVA"
        verbose_name_plural = "Taux TVA"
        ordering = ['valeur']
        unique_together = [('societe', 'nom')]
        constraints = [
            models.UniqueConstraint(
                fields=['societe', 'valeur'],
                name='unique_taux_valeur_par_societe'
            )
        ]

    def __str__(self):
        return f"{self.nom} ({self.valeur}%)"

    # Méthodes existantes conservées
    @classmethod
    def get_default(cls, societe):
        return cls.objects.filter(societe=societe).order_by('-est_defaut', 'valeur').first()

    @classmethod
    def get_taux_zero(cls, societe):
        return cls.objects.filter(societe=societe, valeur=Decimal('0.000')).first()
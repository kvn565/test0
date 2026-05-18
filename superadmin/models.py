# superadmin/models.py — VERSION FINALE CORRIGÉE
import hashlib
import hmac
import secrets
from datetime import date, timedelta
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from societe.models import Societe


# ═══════════════════════════════════════════════════════════════
#  UTILISATEUR
# ═══════════════════════════════════════════════════════════════

class Utilisateur(AbstractUser):
    nom     = models.CharField("Nom",      max_length=100)
    postnom = models.CharField("Post-nom", max_length=100)
    prenom  = models.CharField("Prénom",   max_length=100)

    TYPES_POSTE = [
        ('DIRECTEUR',  'Directeur Général'),
        ('COMPTABLE',  'Comptable'),
        ('VENDEUR',    'Vendeur'),
        ('MAGASINIER', 'Magasinier'),
        ('ASSISTANT',  'Assistant'),
        ('AUTRE',      'Autre'),
    ]
    type_poste = models.CharField("Type de poste", max_length=20,
                                  choices=TYPES_POSTE, default='VENDEUR')
    photo = models.ImageField("Photo de profil", upload_to='users/', null=True, blank=True)

    societe = models.ForeignKey(
        Societe, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='utilisateurs',
        verbose_name="Société",
    )

    # Droits — Stock
    droit_stock_categorie   = models.BooleanField("Droit : Catégories",    default=False)
    droit_stock_produit     = models.BooleanField("Droit : Produits",      default=False)
    droit_stock_fournisseur = models.BooleanField("Droit : Fournisseurs",  default=False)
    droit_stock_entree      = models.BooleanField("Droit : Entrées stock", default=False)
    droit_stock_sortie      = models.BooleanField("Droit : Sorties stock", default=False)

    # Droits — Facturation
    droit_facture_pnb         = models.BooleanField("Droit : PNB",          default=False)
    droit_facture_fdnb        = models.BooleanField("Droit : FDNB",         default=False)
    droit_facture_particulier = models.BooleanField("Droit : Particuliers", default=False)

    # Autres droits
    droit_devis    = models.BooleanField("Droit : Devis",    default=False)
    droit_rapports = models.BooleanField("Droit : Rapports", default=True)

    date_creation = models.DateTimeField("Date de création", auto_now_add=True)
    actif         = models.BooleanField("Compte actif", default=True)

    class Meta:
        verbose_name        = "Utilisateur"
        verbose_name_plural = "Utilisateurs"
        ordering            = ['nom', 'prenom']

    def __str__(self):
        return f"{self.nom} {self.postnom} {self.prenom} ({self.username})"

    @property
    def nom_complet(self):
        return f"{self.nom} {self.postnom} {self.prenom}"

    @property
    def initiales(self):
        if self.nom and self.prenom:
            return f"{self.nom[0]}{self.prenom[0]}".upper()
        return "??"

    def a_droit_stock_complet(self):
        return all([self.droit_stock_categorie, self.droit_stock_produit,
                    self.droit_stock_fournisseur, self.droit_stock_entree,
                    self.droit_stock_sortie])

    def a_droit_facture_complet(self):
        return all([self.droit_facture_pnb, self.droit_facture_fdnb,
                    self.droit_facture_particulier])


# ═══════════════════════════════════════════════════════════════
#  HISTORIQUE CONNEXION
# ═══════════════════════════════════════════════════════════════

class HistoriqueConnexion(models.Model):
    utilisateur      = models.ForeignKey(Utilisateur, on_delete=models.CASCADE, related_name='connexions')
    date_connexion   = models.DateTimeField("Date de connexion",   auto_now_add=True)
    date_deconnexion = models.DateTimeField("Date de déconnexion", null=True, blank=True)
    adresse_ip       = models.GenericIPAddressField("Adresse IP",  null=True, blank=True)
    user_agent       = models.TextField("User Agent", blank=True)

    class Meta:
        verbose_name        = "Historique de connexion"
        verbose_name_plural = "Historiques de connexion"
        ordering            = ['-date_connexion']

    def __str__(self):
        return f"{self.utilisateur.username} - {self.date_connexion}"

    @property
    def duree_session(self):
        if self.date_deconnexion:
            return self.date_deconnexion - self.date_connexion
        return None

    @property
    def duree_formatee(self):
        duree = self.duree_session
        if not duree:
            return "En cours"
        total = int(duree.total_seconds())
        h, m  = total // 3600, (total % 3600) // 60
        return f"{h}h {m}min" if h > 0 else f"{m}min"

    def terminer_session(self):
        if not self.date_deconnexion:
            self.date_deconnexion = timezone.now()
            self.save()


# ═══════════════════════════════════════════════════════════════
#  BACKUP
# ═══════════════════════════════════════════════════════════════

class Backup(models.Model):
    TYPE_BACKUP    = [('COMPLET', 'Backup Complet'), ('PARTIEL', 'Backup Partiel')]
    date_backup    = models.DateTimeField("Date de backup", auto_now_add=True)
    effectue_par   = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True)
    type_backup    = models.CharField("Type", max_length=20, choices=TYPE_BACKUP, default='COMPLET')
    fichier        = models.FileField("Fichier", upload_to='backups/', null=True, blank=True)
    taille_fichier = models.BigIntegerField("Taille (octets)", null=True, blank=True)
    succes         = models.BooleanField("Succès", default=True)
    message        = models.TextField("Message/Erreur", blank=True)

    class Meta:
        verbose_name        = "Backup"
        verbose_name_plural = "Backups"
        ordering            = ['-date_backup']

    def __str__(self):
        return f"Backup {self.type_backup} - {self.date_backup.strftime('%Y-%m-%d %H:%M')}"

    @property
    def taille_lisible(self):
        if not self.taille_fichier:
            return "—"
        size = self.taille_fichier
        for unit in ['o', 'Ko', 'Mo', 'Go']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} To"


# ═══════════════════════════════════════════════════════════════
#  CLÉ D'ACTIVATION
# ═══════════════════════════════════════════════════════════════

class CleActivation(models.Model):
    """
    Clé d'activation liée à UNE société spécifique (nom + NIF).
    Format : {NOM3}-{NIF4}-{PERIODE}-{ALEA6}
    ex: SOD-4567-12M-AB3D4E
    """

    TYPE_PLAN = [
        ('ESSAI',       'Essai gratuit (14 jours)'),
        ('1MOIS',       '1 Mois'),
        ('STARTER',     'Starter (6 mois)'),
        ('BUSINESS',    'Business (12 mois)'),
        ('ENTERPRISE',  'Enterprise (24 mois)'),
    ]

    cle_visible    = models.CharField(max_length=50, unique=True, editable=False)
    empreinte_hmac = models.CharField(max_length=64, editable=False, blank=True)

    societe = models.ForeignKey(
        Societe, on_delete=models.CASCADE,
        related_name='cles_activation',
        verbose_name="Société",
        help_text="La clé est créée spécifiquement pour cette société (nom + NIF).",
    )

    type_plan  = models.CharField("Type de plan", max_length=20,
                                   choices=TYPE_PLAN, default='STARTER')
    duree_mois = models.PositiveSmallIntegerField(
        "Durée (mois)", default=6,
        help_text="Calculé automatiquement depuis type_plan. 0 = essai 14 jours.",
    )

    STATUT = [
        ('DISPONIBLE', 'Disponible — prête à être remise au chef'),
        ('ACTIVE',     'Active — le chef a activé son accès'),
        ('EXPIREE',    'Expirée'),
        ('REVOQUEE',   "Révoquée par l'admin"),
    ]
    statut = models.CharField(
        "Statut", max_length=20, choices=STATUT, default='DISPONIBLE',
    )

    date_debut = models.DateTimeField("Valide à partir du", default=timezone.now)
    date_fin   = models.DateTimeField("Valide jusqu'au", null=True, blank=True)

    active = models.BooleanField("Activée par l'admin", default=True)

    utilisee = models.BooleanField("Utilisée par le chef", default=False)
    date_utilisation = models.DateTimeField("Date d'activation", null=True, blank=True)

    cree_par          = models.CharField(max_length=100, default='superadmin')
    date_creation     = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    motif_revocation  = models.TextField(blank=True)
    notes             = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name        = "Clé d'activation"
        verbose_name_plural = "Clés d'activation"
        ordering            = ['-date_creation']

    def __str__(self):
        statut = "✅" if self.utilisee else "🔑"
        return f"{statut} {self.cle_visible} — {self.societe.nom} [{self.label_plan}]"

    # ── Génération du code ───────────────────────────────────────

    def generer_cle_unique(self):
        alphabet = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'

        nom_clean  = ''.join(c for c in self.societe.nom.upper() if c.isalpha())
        nom_prefix = (nom_clean + 'SOC')[:3]

        nif_digits = ''.join(c for c in self.societe.nif if c.isdigit())
        nif_suffix = nif_digits[-4:] if len(nif_digits) >= 4 else nif_digits.zfill(4)

        periodes = {'ESSAI': '14J', '1MOIS': '1M', 'STARTER': '6M',
                    'BUSINESS': '12M', 'ENTERPRISE': '24M'}
        periode  = periodes.get(self.type_plan, '6M')

        while True:
            alea = ''.join(secrets.choice(alphabet) for _ in range(6))
            code = f"{nom_prefix}-{nif_suffix}-{periode}-{alea}"
            if not CleActivation.objects.filter(cle_visible=code).exists():
                return code

    # ── Save ─────────────────────────────────────────────────────

    def save(self, *args, **kwargs):
        plan_to_duree = {
            'ESSAI':      14,
            '1MOIS':      30,
            'STARTER':    182,
            'BUSINESS':   365,
            'ENTERPRISE': 730,
        }
        duree_jours = plan_to_duree.get(self.type_plan, 182)

        if self.type_plan == '1MOIS':
            self.duree_mois = 1
        elif self.type_plan == 'ESSAI':
            self.duree_mois = 0
        elif self.type_plan == 'AUTRE':
            if self.date_debut and self.date_fin:
                delta = self.date_fin - self.date_debut
                self.duree_mois = max(1, delta.days // 30)
            else:
                self.duree_mois = 0
        else:
            plan_to_mois = {'STARTER': 6, 'BUSINESS': 12, 'ENTERPRISE': 24}
            self.duree_mois = plan_to_mois.get(self.type_plan, 6)

        if not self.date_debut:
            self.date_debut = timezone.now()

        if self.type_plan != 'AUTRE' or not self.date_fin:
            self.date_fin = self.date_debut + timedelta(days=duree_jours)

        if not self.cle_visible:
            self.cle_visible = self.generer_cle_unique()
        if not self.empreinte_hmac:
            self.empreinte_hmac = self._hmac(self.cle_visible, self.societe.nif)

        self.statut = self._calculer_statut()

        super().save(*args, **kwargs)

    # ── Statut ───────────────────────────────────────────────────

    def _calculer_statut(self):
        """
        ✅ CORRECTION : on compare date à date (localdate) pour éviter
        qu'une licence expire avant minuit à cause du décalage horaire UTC.
        """
        if not self.active:
            return 'REVOQUEE'

        if self.utilisee:
            # Vérifie si la clé active est vraiment encore valide (date locale)
            if self.date_fin and timezone.localdate() > self.date_fin.date():
                return 'EXPIREE'
            return 'ACTIVE'

        if self.date_fin and timezone.localdate() > self.date_fin.date():
            return 'EXPIREE'

        return 'DISPONIBLE'

    # ── Validité ─────────────────────────────────────────────────

    def est_valide(self):
        """True si la clé peut être utilisée maintenant."""
        if self.statut != 'DISPONIBLE':
            return False
        if not self.date_debut or not self.date_fin:
            return False
        now = timezone.now()
        return self.date_debut <= now <= self.date_fin

    # ── Vérification NIF ─────────────────────────────────────────

    def verifier_nif_societe(self, nif_saisi):
        nif_societe = self.societe.nif.strip().lower()
        nif_saisi   = (nif_saisi or '').strip().lower()
        return nif_societe == nif_saisi

    # ── Activation ───────────────────────────────────────────────

    def activer(self):
        self.utilisee         = True
        self.statut           = 'ACTIVE'
        self.date_utilisation = timezone.now()
        self.save()

    def utiliser(self, societe):
        self.activer()

    def lier_societe(self, societe):
        self.activer()

    # ── Jours restants ───────────────────────────────────────────

    @property
    def jours_restants(self):
        """
        ✅ CORRECTION PRINCIPALE :
        On compare date_fin.date() (date pure) à timezone.localdate() (date locale)
        et on calcule le delta en jours entiers — sans troncature d'heures.

        AVANT (bugué) :
            delta = self.date_fin - timezone.now()
            return max(0, delta.days)
            → timedelta.days tronque les heures : le jour J à 08h00
              delta.days = 0 alors qu'il reste encore 16h → modal déclenché trop tôt.

        APRÈS (correct) :
            delta = self.date_fin.date() - timezone.localdate()
            → date - date = nombre de jours entiers, sans ambiguïté d'heure.
            → Le modal se déclenche uniquement quand jours_restants == 0,
              c'est-à-dire le lendemain de date_fin.date().
        """
        if not self.date_fin:
            return 0
        if self.statut not in ('DISPONIBLE', 'ACTIVE'):
            return 0
        delta = self.date_fin.date() - timezone.localdate()
        return max(0, delta.days)

    # ── Statut lisible ───────────────────────────────────────────

    def get_statut_display(self):
        now = timezone.now()

        if not self.societe.utilisateurs.filter(type_poste='DIRECTEUR').exists():
            return "🔒 Clé de licence inactive (chef non créé)"

        if self.statut == 'REVOQUEE':
            return "❌ Révoquée par l'admin"

        if self.date_fin and now > self.date_fin:
            return f"⏰ Expirée le {self.date_fin.strftime('%d/%m/%Y')}"

        if self.statut == 'ACTIVE':
            return f"✅ Activée par '{self.societe.nom}' ({self.label_plan})"

        if self.statut == 'DISPONIBLE':
            return f"🟢 Prête — NIF: {self.societe.nif} ({self.jours_restants} jours restants)"

        return "⏳ Statut inconnu"

    # ── Prolonger ────────────────────────────────────────────────

    def prolonger(self, jours):
        if not self.utilisee and self.date_fin:
            self.date_fin = self.date_fin + timedelta(days=jours)
            self.save()

    # ── Vérification setup ───────────────────────────────────────

    @classmethod
    def verifier_pour_setup(cls, cle_saisie, nif_saisi):
        now = timezone.now()
        try:
            obj = cls.objects.select_related('societe').get(
                cle_visible=cle_saisie.strip().upper()
            )
        except cls.DoesNotExist:
            return False, "Clé d'activation invalide.", None

        if obj.statut == 'ACTIVE':
            return False, "Cette clé a déjà été utilisée.", None
        if obj.statut == 'REVOQUEE':
            return False, "Clé désactivée par l'administrateur.", None
        if obj.statut == 'EXPIREE':
            return False, f"Clé expirée le {obj.date_fin.strftime('%d/%m/%Y')}.", None
        if not obj.verifier_nif_societe(nif_saisi):
            return False, f"Cette clé est réservée pour le NIF {obj.societe.nif}.", None
        if obj.empreinte_hmac:
            if not hmac.compare_digest(cls._hmac(obj.cle_visible, obj.societe.nif),
                                       obj.empreinte_hmac):
                return False, "Intégrité de la clé compromise.", None
        if not obj.date_fin:
            return False, "Clé sans date d'expiration.", None
        if now > obj.date_fin:
            return False, f"Clé expirée le {obj.date_fin.strftime('%d/%m/%Y')}.", None
        if obj.date_debut and now < obj.date_debut:
            return False, f"Clé active à partir du {obj.date_debut.strftime('%d/%m/%Y')}.", None

        return True, f"Clé valide jusqu'au {obj.date_fin.strftime('%d/%m/%Y')}.", obj

    # ── Fabrique essai ───────────────────────────────────────────

    @classmethod
    def creer_essai(cls, societe, cree_par='superadmin'):
        now = timezone.now()
        cle = cls(
            societe          = societe,
            type_plan        = 'ESSAI',
            date_debut       = now,
            date_fin         = now + timedelta(days=14),
            active           = True,
            utilisee         = True,
            statut           = 'ACTIVE',
            date_utilisation = now,
            cree_par         = cree_par,
            notes            = "Essai gratuit 14 jours — généré automatiquement",
        )
        cle.save()
        return cle

    # ── Utilitaires ──────────────────────────────────────────────

    @classmethod
    def _hmac(cls, cle_visible, nif):
        from django.conf import settings
        secret = settings.SECRET_KEY.encode()
        msg    = f"{cle_visible}:{nif}".encode()
        return hmac.new(secret, msg, hashlib.sha256).hexdigest()

    @property
    def label_plan(self):
        labels = {
            'ESSAI':      'Essai 14j',
            '1MOIS':      '1 Mois',
            'STARTER':    'Starter 6m',
            'BUSINESS':   'Business 12m',
            'ENTERPRISE': 'Enterprise 24m',
        }
        return labels.get(self.type_plan, self.type_plan)

    @property
    def est_essai(self):
        return self.type_plan == 'ESSAI'


# ═══════════════════════════════════════════════════════════════
#  AUDIT CLÉ
# ═══════════════════════════════════════════════════════════════

class AuditCle(models.Model):
    ACTION = [
        ('CREEE',     'Clé créée'),
        ('ACTIVEE',   'Clé activée'),
        ('REVOQUEE',  'Clé révoquée'),
        ('ECHEC',     'Tentative échouée'),
        ('SUSPENDUE', 'Société suspendue'),
        ('REACTIVEE', 'Société réactivée'),
        ('PROLONGEE', 'Clé prolongée'),
    ]

    cle     = models.ForeignKey(CleActivation, on_delete=models.SET_NULL, null=True, blank=True)
    societe = models.ForeignKey(
        Societe, on_delete=models.CASCADE,
        related_name='audits',
        null=True, blank=True,
    )
    action      = models.CharField(max_length=20, choices=ACTION)
    message     = models.TextField(blank=True)
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    date_action = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_action']

    def __str__(self):
        nom = self.societe.nom if self.societe else 'N/A'
        d   = self.date_action.strftime('%d/%m/%Y %H:%M')
        return f"{nom} | {self.action} | {d}"

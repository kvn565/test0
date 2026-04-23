# superadmin/models.py — VERSION FINALE
# ✅ Adapté du projet restaurant (subscriptions/models.py)
# ✅ Aligné sur PHP WIBABI (type_plan, duree_mois, format code)

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
#  ✅ Structure calquée sur le projet restaurant (subscriptions/models.py)
#  ✅ Champs PHP WIBABI : type_plan, duree_mois, format code
# ═══════════════════════════════════════════════════════════════

class CleActivation(models.Model):
    """
    Clé d'activation liée à UNE société spécifique (nom + NIF).

    Le superadmin :
      1. Enregistre la société
      2. Génère une clé pour cette société (avec durée variable)
      3. Donne la clé au chef
    Le chef entre la clé + son NIF pour activer l'accès.

    Format de la clé : {NOM3}-{NIF4}-{PERIODE}-{ALEA6}
      ex: SOD-4567-12M-AB3D4E  (SODECO, NIF ...4567, Business 12 mois)
      ex: SOD-4567-14J-AB3D4E  (SODECO, NIF ...4567, Essai 14 jours)
    """

    TYPE_PLAN = [
        ('ESSAI',      'Essai gratuit (14 jours)'),
        ('STARTER',    'Starter (6 mois)'),
        ('BUSINESS',   'Business (12 mois)'),
        ('ENTERPRISE', 'Enterprise (24 mois)'),
    ]

    # ── Code unique intégrant nom + NIF ─────────────────────────
    cle_visible    = models.CharField(max_length=50, unique=True, editable=False)
    empreinte_hmac = models.CharField(max_length=64, editable=False, blank=True)

    # ── Société : OBLIGATOIRE dès la création ───────────────────
    societe = models.ForeignKey(
        Societe, on_delete=models.CASCADE,
        related_name='cles_activation',
        verbose_name="Société",
        help_text="La clé est créée spécifiquement pour cette société (nom + NIF).",
    )

    # ── Plan & durée ─────────────────────────────────────────────
    type_plan  = models.CharField("Type de plan", max_length=20,
                                   choices=TYPE_PLAN, default='STARTER')
    duree_mois = models.PositiveSmallIntegerField(
        "Durée (mois)", default=6,
        help_text="Calculé automatiquement depuis type_plan. 0 = essai 14 jours.",
    )

    # ── Statut ───────────────────────────────────────────────────
    STATUT = [
        ('DISPONIBLE', 'Disponible — prête à être remise au chef'),
        ('ACTIVE',     'Active — le chef a activé son accès'),
        ('EXPIREE',    'Expirée'),
        ('REVOQUEE',   "Révoquée par l'admin"),
    ]
    statut = models.CharField(
        "Statut", max_length=20, choices=STATUT, default='DISPONIBLE',
        help_text="Mis à jour automatiquement. DISPONIBLE → chef reçoit la clé. ACTIVE → chef a activé.",
    )

    # ── Période de validité ──────────────────────────────────────
    date_debut = models.DateTimeField("Valide à partir du", default=timezone.now)
    date_fin   = models.DateTimeField("Valide jusqu'au", null=True, blank=True)

    # ── Contrôle admin ───────────────────────────────────────────
    active = models.BooleanField(
        "Activée par l'admin", default=True,
        help_text="L'admin peut désactiver/réactiver manuellement",
    )

    # ── Utilisation ──────────────────────────────────────────────
    utilisee = models.BooleanField(
        "Utilisée par le chef", default=False,
        help_text="True quand le chef a entré la clé et activé son accès",
    )
    date_utilisation = models.DateTimeField(
        "Date d'activation", null=True, blank=True,
    )

    # ── Audit ────────────────────────────────────────────────────
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

    # =========================
    # GÉNÉRATION CODE
    # Format : {NOM3}-{NIF4}-{PERIOD}-{ALEA6}
    # NOM3  = 3 premières lettres alpha du nom de la société
    # NIF4  = 4 derniers chiffres du NIF
    # PERIOD= 14J / 6M / 12M / 24M
    # ALEA6 = 6 caractères aléatoires (sans ambigüités 0/O, 1/I)
    # Exemple : SOD-4567-12M-AB3D4E
    # =========================

    def generer_cle_unique(self):
        alphabet = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'

        # Préfixe NOM : 3 premières lettres alpha (majuscules)
        nom_clean  = ''.join(c for c in self.societe.nom.upper() if c.isalpha())
        nom_prefix = (nom_clean + 'SOC')[:3]   # fallback 'SOC' si nom trop court

        # Suffixe NIF : 4 derniers chiffres du NIF
        nif_digits = ''.join(c for c in self.societe.nif if c.isdigit())
        nif_suffix = nif_digits[-4:] if len(nif_digits) >= 4 else nif_digits.zfill(4)

        # Période
        periodes = {'ESSAI': '14J', 'STARTER': '6M', 'BUSINESS': '12M', 'ENTERPRISE': '24M'}
        periode  = periodes.get(self.type_plan, '6M')

        while True:
            alea = ''.join(secrets.choice(alphabet) for _ in range(6))
            code = f"{nom_prefix}-{nif_suffix}-{periode}-{alea}"
            if not CleActivation.objects.filter(cle_visible=code).exists():
                return code

    # =========================
    # SAVE
    # =========================

    def save(self, *args, **kwargs):
        # 1️⃣ Calculer la durée et date_fin si non défini
        plan_to_mois = {'ESSAI': 0, 'STARTER': 6, 'BUSINESS': 12, 'ENTERPRISE': 24}
        self.duree_mois = plan_to_mois.get(self.type_plan, 6)

        now = timezone.now()

        if not self.date_debut:
            self.date_debut = now

        if not self.date_fin:
            durees_jours = {'ESSAI': 14, 'STARTER': 182, 'BUSINESS': 365, 'ENTERPRISE': 730}
            self.date_fin = self.date_debut + timedelta(days=durees_jours.get(self.type_plan, 182))

        # 2️⃣ Générer la clé si nécessaire
        if not self.cle_visible:
            self.cle_visible = self.generer_cle_unique()
        if not self.empreinte_hmac:
            self.empreinte_hmac = self._hmac(self.cle_visible, self.societe.nif)

        # 3️⃣ Synchroniser le statut
        if not self.active:
            self.statut = 'REVOQUEE'
        elif self.utilisee:
            self.statut = 'ACTIVE'
        elif self.date_fin:
            # ✅ CORRECTION : comparaison robuste date_fin vs now
            # date_fin peut être un objet date OU datetime (selon la source du formulaire)
            # On normalise en datetime aware pour éviter les erreurs de type
            from datetime import datetime as dt
            fin = self.date_fin
            if isinstance(fin, dt):
                # Déjà un datetime — s'assurer qu'il est timezone-aware
                if timezone.is_naive(fin):
                    fin = timezone.make_aware(fin)
            else:
                # C'est un objet date → convertir en datetime aware à minuit
                fin = timezone.make_aware(dt.combine(fin, dt.min.time()))
            self.statut = 'EXPIREE' if fin < now else 'DISPONIBLE'
        else:
            self.statut = 'DISPONIBLE'

        super().save(*args, **kwargs)

    # =========================
    # VALIDITÉ
    # =========================

    def est_valide(self):
        """Retourne True si la clé peut être utilisée maintenant (statut DISPONIBLE + dates OK)."""
        if self.statut != 'DISPONIBLE':
            return False
        if not self.date_debut or not self.date_fin:
            return False
        now = timezone.now()
        return self.date_debut <= now <= self.date_fin

    # =========================
    # VÉRIFIER NIF
    # Le chef entre son NIF → on vérifie qu'il correspond à celui de la société liée
    # =========================

    def verifier_nif_societe(self, nif_saisi):
        """
        Vérifie que le NIF saisi correspond au NIF de la société liée à cette clé.
        Insensible à la casse et aux espaces.
        """
        nif_societe = self.societe.nif.strip().lower()
        nif_saisi   = (nif_saisi or '').strip().lower()
        return nif_societe == nif_saisi

    # =========================
    # ACTIVER — appelé quand le chef utilise sa clé
    # =========================

    def activer(self):
        """
        Marque la clé comme utilisée (le chef a activé son accès).
        La société est déjà liée depuis la création de la clé.
        """
        self.utilisee         = True
        self.statut           = 'ACTIVE'
        self.date_utilisation = timezone.now()
        self.save()

    # Alias pour compatibilité avec l'ancien code
    def utiliser(self, societe):
        self.activer()

    def lier_societe(self, societe):
        self.activer()

    # =========================
    # JOURS RESTANTS
    # =========================

    @property
    def jours_restants(self):
        if not self.date_fin:
            return 0
        if self.statut not in ('DISPONIBLE', 'ACTIVE'):
            return 0
        delta = self.date_fin - timezone.now()
        return max(0, delta.days)

    # =========================
    # STATUT LISIBLE
    # =========================

    def get_statut_display(self):
        now = timezone.now()

        # 🔒 Aucun chef encore créé
        if not self.societe.utilisateurs.filter(type_poste='DIRECTEUR').exists():
            return "🔒 Clé de licence inactive (chef non créé)"

        # ❌ Révoquée
        if self.statut == 'REVOQUEE':
            return "❌ Révoquée par l'admin"

        # ⏰ Expirée
        if self.date_fin and now > self.date_fin:
            return f"⏰ Expirée le {self.date_fin.strftime('%d/%m/%Y')}"

        # ✅ Active
        if self.statut == 'ACTIVE':
            return f"✅ Activée par '{self.societe.nom}' ({self.label_plan})"

        # 🟢 Disponible
        if self.statut == 'DISPONIBLE':
            return f"🟢 Prête — NIF: {self.societe.nif} ({self.jours_restants} jours restants)"

        return "⏳ Statut inconnu"

    # =========================
    # PROLONGER
    # =========================

    def prolonger(self, jours):
        """Prolonge la clé de N jours (uniquement si non utilisée)."""
        if not self.utilisee and self.date_fin:
            self.date_fin = self.date_fin + timedelta(days=jours)
            self.save()

    # =========================
    # VÉRIFICATION SETUP
    # Appelé quand le chef saisit sa clé + son NIF pour activer l'application
    # =========================

    @classmethod
    def verifier_pour_setup(cls, cle_saisie, nif_saisi):
        """
        Vérifie une clé lors du setup initial.
        Le chef saisit :
          - La clé reçue du superadmin (ex: SOD-4567-12M-AB3D4E)
          - Le NIF de sa société
        On vérifie que le NIF correspond à celui de la société liée à la clé.
        """
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

    # =========================
    # FABRIQUE — ESSAI
    # Génère et lie immédiatement une clé d'essai 14 jours à une société
    # =========================

    @classmethod
    def creer_essai(cls, societe, cree_par='superadmin'):
        """Génère et active immédiatement une clé d'essai de 14 jours."""
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

    # =========================
    # UTILITAIRES
    # =========================

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

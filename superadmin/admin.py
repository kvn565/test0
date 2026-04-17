from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from .models import Utilisateur, HistoriqueConnexion, Backup, CleActivation, AuditCle
from societe.models import Societe
from django.urls import reverse_lazy


admin.site.site_url = reverse_lazy('superadmin:dashboard') 
# ═══════════════════════════════════════════════════════════════
#  UTILISATEUR
# ═══════════════════════════════════════════════════════════════
@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    list_display    = ('username', 'nom', 'postnom', 'prenom', 'type_poste', 'societe', 'actif', 'is_superuser', 'date_creation')
    list_filter     = ('type_poste', 'actif', 'is_superuser', 'societe')
    search_fields   = ('username', 'nom', 'postnom', 'prenom', 'email')
    ordering        = ('-date_creation',)
    readonly_fields = ('date_creation',)

    fieldsets = (
        ("Informations personnelles", {
            'fields': ('username', 'password', 'nom', 'postnom', 'prenom', 'email', 'photo')
        }),
        ("Société & Poste", {
            'fields': ('societe', 'type_poste', 'actif')
        }),
        ("Droits Stock", {
            'fields': ('droit_stock_categorie', 'droit_stock_produit', 'droit_stock_fournisseur', 'droit_stock_entree', 'droit_stock_sortie')
        }),
        ("Droits Facturation", {
            'fields': ('droit_facture_pnb', 'droit_facture_fdnb', 'droit_facture_particulier')
        }),
        ("Autres droits", {
            'fields': ('droit_devis', 'droit_rapports')
        }),
        ("Permissions système", {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ("Dates", {
            'fields': ('last_login', 'date_creation')
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'nom', 'postnom', 'prenom', 'email'),
        }),
        ("Société & Poste", {
            'classes': ('wide',),
            'fields': ('societe', 'type_poste', 'actif'),
        }),
    )


# ═══════════════════════════════════════════════════════════════
#  HISTORIQUE CONNEXION
# ═══════════════════════════════════════════════════════════════
@admin.register(HistoriqueConnexion)
class HistoriqueConnexionAdmin(admin.ModelAdmin):
    list_display    = ('utilisateur', 'date_connexion', 'date_deconnexion', 'duree_formatee', 'adresse_ip')
    list_filter     = ('date_connexion',)
    search_fields   = ('utilisateur__username', 'adresse_ip')
    readonly_fields = ('utilisateur', 'date_connexion', 'date_deconnexion', 'adresse_ip', 'user_agent')
    ordering        = ('-date_connexion',)


# ═══════════════════════════════════════════════════════════════
#  BACKUP
# ═══════════════════════════════════════════════════════════════
@admin.register(Backup)
class BackupAdmin(admin.ModelAdmin):
    list_display    = ('date_backup', 'type_backup', 'effectue_par', 'taille_lisible', 'succes')
    list_filter     = ('type_backup', 'succes', 'date_backup')
    search_fields   = ('effectue_par__username', 'message')
    readonly_fields = ('date_backup', 'effectue_par', 'type_backup', 'fichier', 'taille_fichier', 'message')
    ordering        = ('-date_backup',)


# ═══════════════════════════════════════════════════════════════
#  CLÉ D'ACTIVATION
# ═══════════════════════════════════════════════════════════════
@admin.register(CleActivation)
class CleActivationAdmin(admin.ModelAdmin):

    list_display = (
        'cle_visible',
        'societe_info',
        'plan_badge',
        'statut_badge',
        'active',
        'date_fin',
        'jours_restants_display',
    )

    list_filter  = ('statut', 'type_plan', 'active', 'date_creation')
    search_fields = ('cle_visible', 'societe__nom', 'societe__nif', 'notes')
    ordering = ('-date_creation',)
    list_editable = ('active',)

    readonly_fields = (
        'cle_visible',
        'empreinte_hmac',
        'statut',
        'duree_mois',
        'utilisee',
        'date_utilisation',
        'date_creation',
        'date_modification',
        'statut_complet',
        'jours_restants_display',
    )

    fieldsets = (
        ('Société liée', {'fields': ('societe',)}),
        ("Clé d'activation", {'fields': ('cle_visible', 'empreinte_hmac', 'active')}),
        ('Plan', {'fields': ('type_plan', 'duree_mois')}),
        ('Période de validité', {'fields': ('date_debut', 'date_fin', 'jours_restants_display')}),
        ('Statut', {'fields': ('statut', 'utilisee', 'date_utilisation', 'statut_complet')}),
        ('Notes', {'fields': ('notes', 'motif_revocation'), 'classes': ('collapse',)}),
        ('Métadonnées', {'fields': ('cree_par', 'date_creation', 'date_modification'), 'classes': ('collapse',)}),
    )

    actions = ['activer_cles', 'desactiver_cles', 'prolonger_30_jours', 'prolonger_90_jours']

    def societe_info(self, obj):
        return format_html(
            '<strong>{}</strong><br><small style="color: gray;">NIF : {}</small>',
            obj.societe.nom,
            obj.societe.nif,
        )
    societe_info.short_description = "Société"

    def statut_badge(self, obj):
        couleurs = {
            'DISPONIBLE': ('#28a745', '🟢 Disponible'),
            'ACTIVE':     ('#007bff', '✅ Active'),
            'EXPIREE':    ('#dc3545', '⏰ Expirée'),
            'REVOQUEE':   ('#6c757d', '❌ Révoquée'),
        }
        color, text = couleurs.get(obj.statut, ('#aaa', obj.statut))
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, text
        )
    statut_badge.short_description = "Statut"

    def plan_badge(self, obj):
        couleurs = {
            'ESSAI':      ('#f59e0b', 'Essai 14j'),
            'STARTER':    ('#10b981', 'Starter 6m'),
            'BUSINESS':   ('#3b82f6', 'Business 12m'),
            'ENTERPRISE': ('#8b5cf6', 'Enterprise 24m'),
        }
        color, text = couleurs.get(obj.type_plan, ('#aaa', obj.type_plan))
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; '
            'border-radius: 10px; font-size: 11px; font-weight: bold;">{}</span>',
            color, text
        )
    plan_badge.short_description = "Plan"

    def jours_restants_display(self, obj):
        jours = obj.jours_restants
        if obj.statut in ('DISPONIBLE', 'ACTIVE') and jours > 0:
            if jours > 30:
                color = "green"
            elif jours > 7:
                color = "orange"
            else:
                color = "red"
            return format_html(
                '<span style="color: {}; font-weight: bold;">{} jours</span>',
                color, jours
            )
        elif obj.statut == 'EXPIREE':
            return format_html('<span style="color: red;">Expirée</span>')
        return format_html('<span style="color: gray;">—</span>')
    jours_restants_display.short_description = "Jours restants"

    def statut_complet(self, obj):
        return format_html('<strong>{}</strong>', obj.get_statut_display())
    statut_complet.short_description = "Statut détaillé"

    def activer_cles(self, request, queryset):
        count = 0
        for cle in queryset.filter(utilisee=False):
            cle.active = True
            cle.save()
            count += 1
        self.message_user(request, f"{count} clé(s) activée(s).")
    activer_cles.short_description = "✅ Activer les clés"

    def desactiver_cles(self, request, queryset):
        count = 0
        for cle in queryset.filter(utilisee=False):
            cle.active = False
            cle.save()
            count += 1
        self.message_user(request, f"{count} clé(s) désactivée(s).")
    desactiver_cles.short_description = "❌ Désactiver les clés"

    def prolonger_30_jours(self, request, queryset):
        from datetime import timedelta
        count = 0
        for cle in queryset.filter(utilisee=False):
            if cle.date_fin:
                cle.date_fin += timedelta(days=30)
                cle.save()
                count += 1
        self.message_user(request, f"{count} clé(s) prolongée(s) de 30 jours.")
    prolonger_30_jours.short_description = "⏰ Prolonger de 30 jours"

    def prolonger_90_jours(self, request, queryset):
        from datetime import timedelta
        count = 0
        for cle in queryset.filter(utilisee=False):
            if cle.date_fin:
                cle.date_fin += timedelta(days=90)
                cle.save()
                count += 1
        self.message_user(request, f"{count} clé(s) prolongée(s) de 90 jours.")
    prolonger_90_jours.short_description = "⏰ Prolonger de 90 jours"

    def has_delete_permission(self, request, obj=None):
        if obj and obj.statut == 'ACTIVE':
            return False
        return super().has_delete_permission(request, obj)


# ═══════════════════════════════════════════════════════════════
#  AUDIT CLÉ
# ═══════════════════════════════════════════════════════════════
@admin.register(AuditCle)
class AuditCleAdmin(admin.ModelAdmin):
    list_display    = ('date_action', 'societe', 'cle', 'action', 'ip_address', 'message_court')
    list_filter     = ('action', 'date_action')
    search_fields   = ('societe__nom', 'societe__nif', 'message', 'ip_address')
    readonly_fields = ('cle', 'societe', 'action', 'message', 'ip_address', 'date_action')
    ordering        = ('-date_action',)

    def message_court(self, obj):
        return (obj.message[:80] + '…') if len(obj.message) > 80 else obj.message
    message_court.short_description = "Message"


# ═══════════════════════════════════════════════════════════════
#  SOCIÉTÉ
# ═══════════════════════════════════════════════════════════════
class CleActivationInline(admin.TabularInline):
    model = CleActivation
    extra = 1
    fields = ('type_plan', 'cle_visible', 'statut', 'date_debut', 'date_fin', 'active', 'notes')
    readonly_fields = ('cle_visible', 'statut', 'duree_mois')
    ordering = ('-date_creation',)
    show_change_link = True


@admin.register(Societe)
class SocieteAdmin(admin.ModelAdmin):

    list_display = (
        'nom',
        'nif',
        'forme',       
        'secteur',
        'telephone',
        'province',
        'centre_fiscale',
        'assujeti_tva',
        'obr_statut_badge',   # ✅ NOUVEAU
        'licence_affichage',
        'date_creation',
    )

    list_filter  = ('centre_fiscale', 'assujeti_tva', 'assujeti_tc', 'province', 'obr_actif')
    search_fields = ('nom', 'nif', 'registre', 'telephone', 'commune', 'quartier')
    ordering = ('-date_creation',)
    readonly_fields = (
        'date_creation', 'date_modification',
        'adresse_complete', 'licence_affichage',
        'obr_statut_badge',   # ✅ NOUVEAU
    )
    inlines = [CleActivationInline]

    fieldsets = (
        ('Identification légale', {
            'fields': ('nom', 'nif','forme','secteur', 'registre', 'boite_postal', 'telephone')
        }),
        ('Adresse', {
            'fields': ('province', 'commune', 'quartier', 'avenue', 'numero', 'adresse_complete')
        }),
        ('Fiscalité', {
            'fields': ('centre_fiscale', 'assujeti_tva', 'assujeti_tc')
        }),
        # ══════════════════════════════════════════════════════════
        #  SECTION OBR — Ajoutée pour l'intégration eBMS
        #  Identifiants fournis par l'OBR lors de l'enregistrement
        #  Contact OBR : 22282525 / innocent.kanyanzira@obr.gov.bi
        # ══════════════════════════════════════════════════════════
        ('🔐 Configuration OBR (eBMS)', {
            'fields': ('obr_actif', 'obr_username', 'obr_password', 'obr_system_id', 'obr_statut_badge'),
            'description': (
                '<strong>Ces informations sont fournies par l\'OBR</strong> lors de l\'enregistrement '
                'du système de facturation électronique.<br>'
                '📞 Tél : 22282525 ou 22282832 &nbsp;|&nbsp; '
                '✉️ innocent.kanyanzira@obr.gov.bi'
            ),
            'classes': ('collapse',),  # Repliée par défaut pour ne pas encombrer
        }),
        ('Licence actuelle', {
            'fields': ('licence_affichage',),
            'description': "Ajoutez une clé d'activation dans le tableau ci-dessous."
        }),
        ('Traçabilité', {
            'fields': ('date_creation', 'date_modification'),
            'classes': ('collapse',)
        }),

        ('💼 Gérant & Paramétrage facturation', {
            'fields': (
                'nom_complet_gerant',
                'numero_depart',
                'email_societe',           # ← ajouté ici
            ),
            'description': (
                'Ces informations sont réservées au superadmin uniquement.<br>'
                'Utilisées pour la facturation, la conformité et les communications officielles.'
            ),
            'classes': ('collapse',),
        }),
    )

    def save_model(self, request, obj, form, change):
        """
        Quand une nouvelle société est créée via l'admin Django,
        on génère automatiquement une clé d'essai 14 jours (comme la vue web).
        """
        is_new = not obj.pk  # True si c'est une création (pas une modification)
        super().save_model(request, obj, form, change)
        if is_new:
            from .models import CleActivation, AuditCle
            cle = CleActivation.creer_essai(obj, cree_par=request.user.username)
            AuditCle.objects.create(
                societe=obj,
                cle=cle,
                action='CREEE',
                message=(
                    f"Société '{obj.nom}' (NIF: {obj.nif}) créée via l'admin Django "
                    f"par {request.user.username}. "
                    f"Clé d'essai 14 jours activée automatiquement : {cle.cle_visible} "
                    f"(expire le {cle.date_fin.strftime('%d/%m/%Y')})."
                ),
            )
            self.message_user(
                request,
                f"✅ Clé d'essai 14 jours générée automatiquement : {cle.cle_visible} "
                f"(expire le {cle.date_fin.strftime('%d/%m/%Y')})."
            )



    actions = [
        'generer_cle_essai', 'generer_cle_starter',
        'generer_cle_business', 'generer_cle_enterprise',
    ]

    # ── Affichage statut OBR ──────────────────────────────────────
       
        # ── Affichage statut OBR ──────────────────────────────────────
        # ── Affichage statut OBR ──────────────────────────────────────
    def obr_statut_badge(self, obj):
        """Badge pour le statut de configuration OBR"""
        if not getattr(obj, 'obr_actif', False):
            return '<span class="badge bg-secondary">⭕ Inactif</span>'
        elif getattr(obj, 'obr_configure', False):
            return '<span class="badge bg-success">✅ Configuré</span>'
        else:
            return '<span class="badge bg-danger">⚠️ Incomplet</span>'

    obr_statut_badge.short_description = "Statut OBR"
    obr_statut_badge.allow_tags = True


    # ── Affichage licence ─────────────────────────────────────────
    def licence_affichage(self, obj):
        """Affichage de la licence actuelle"""
        cle = obj.cle_active
        if cle:
            couleurs = {
                'ESSAI':      '#f59e0b',
                'STARTER':    '#10b981',
                'BUSINESS':   '#3b82f6',
                'ENTERPRISE': '#8b5cf6',
            }
            color = couleurs.get(cle.type_plan, '#aaa')
            return format_html(
                '<span style="background: {}; color: white; padding: 2px 8px; '
                'border-radius: 10px; font-size: 11px; font-weight: bold;">'
                '{} — expire le {}</span>',
                color,
                cle.label_plan,
                cle.date_fin.strftime('%d/%m/%Y') if cle.date_fin else '?',
            )
        
        return '<span style="color: gray;">Aucune licence active</span>'

    licence_affichage.short_description = "Licence"

    # ── Actions ───────────────────────────────────────────────────
    def generer_cle_essai(self, request, queryset):
        count = 0
        for societe in queryset:
            CleActivation.creer_essai(societe, cree_par=request.user.username)
            count += 1
        self.message_user(request, f"✅ {count} clé(s) d'essai générée(s) et activée(s).")
    generer_cle_essai.short_description = "🟡 Générer clé Essai 14j"

    def generer_cle_starter(self, request, queryset):
        self._generer_cles(request, queryset, 'STARTER')
    generer_cle_starter.short_description = "🟢 Générer clé Starter 6 mois"

    def generer_cle_business(self, request, queryset):
        self._generer_cles(request, queryset, 'BUSINESS')
    generer_cle_business.short_description = "🔵 Générer clé Business 12 mois"

    def generer_cle_enterprise(self, request, queryset):
        self._generer_cles(request, queryset, 'ENTERPRISE')
    generer_cle_enterprise.short_description = "🟣 Générer clé Enterprise 24 mois"

    def _generer_cles(self, request, queryset, type_plan):
        count = 0
        for societe in queryset:
            CleActivation.objects.create(
                societe   = societe,
                type_plan = type_plan,
                cree_par  = request.user.username,
            )
            count += 1
        labels = {'STARTER': 'Starter 6m', 'BUSINESS': 'Business 12m', 'ENTERPRISE': 'Enterprise 24m'}
        self.message_user(
            request,
            f"✅ {count} clé(s) {labels[type_plan]} générée(s) — à remettre aux chefs de société."
        )

# superadmin/views.py — VERSION FINALE
# LOGIQUE CLÉS :
#   superadmin enregistre société → clé essai 14j activée AUTOMATIQUEMENT
#   le chef s'inscrit lui-même via /accounts/register/ avec son NIF
#   le NIF doit avoir une clé ACTIVE sinon inscription refusée
#   après 14j d'essai, superadmin génère une clé payante → chef la saisit dans l'appli

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse, FileResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.core import management
from django.conf import settings
from django.utils import timezone
from django.core.paginator import Paginator
from datetime import date, timedelta
import calendar, os


from .models import Utilisateur, HistoriqueConnexion, Backup, CleActivation, AuditCle
from societe.models import Societe
from .forms import (
    SocieteForm, CleActivationForm, RevoquerCleForm,
    InscriptionChefForm, ClePayanteForm,
    UtilisateurCreationForm, UtilisateurModificationForm, ChangerMotDePasseForm,
    SocieteGeranceForm,          # ← Pour gérer gérant, email, numéro de départ
    SocieteAdminConfigForm,
)


# ═══════════════════════════════════════════════════════════════
#  DÉCORATEURS
# ═══════════════════════════════════════════════════════════════

def superadmin_required(view_func):
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, "Accès réservé à l'administrateur.")
            return redirect('accounts:login')
        return view_func(request, *args, **kwargs)
    return wrapper

def est_superadmin(user):
    return user.is_superuser


# ═══════════════════════════════════════════════════════════════
#  DASHBOARD
#  ✅ CORRECTION : stats enrichies (essai, actives, expirant)
#     Aligné sur index.php de WIBABI
# ═══════════════════════════════════════════════════════════════

@superadmin_required
def dashboard(request):
    today    = date.today()
    societes = Societe.objects.all()

    # Sociétés avec licence active (non-essai)
    societes_actives = Societe.objects.filter(
        cles_activation__statut='ACTIVE',
        cles_activation__date_debut__lte=today,
        cles_activation__date_fin__gte=today,
    ).distinct().count()

    # ✅ AJOUT : sociétés en période d'essai (type_plan=ESSAI, statut=ACTIVE)
    societes_essai = Societe.objects.filter(
        cles_activation__statut='ACTIVE',
        cles_activation__type_plan='ESSAI',
        cles_activation__date_fin__gte=today,
    ).distinct().count()

    # ✅ AJOUT : clés disponibles (non encore attribuées) — comme PHP
    cles_disponibles = CleActivation.objects.filter(statut='DISPONIBLE').count()

    stats = {
        'total_societes':   societes.count(),
        'societes_actives': societes_actives,
        'societes_essai':   societes_essai,           # ✅ AJOUT
        'cles_disponibles': cles_disponibles,         # ✅ AJOUT
        'cles_actives':     CleActivation.objects.filter(
                                statut='ACTIVE', date_debut__lte=today, date_fin__gte=today
                            ).count(),
        'cles_expirant':    CleActivation.objects.filter(
                                statut='ACTIVE',
                                date_fin__range=(today, today + timedelta(days=7))
                            ).count(),
        'total_users':      Utilisateur.objects.count(),
    }

    expiration_proche = CleActivation.objects.filter(
        statut='ACTIVE', date_fin__range=(today, today + timedelta(days=7))
    ).select_related('societe').order_by('date_fin')

    derniers_audits = AuditCle.objects.select_related('societe', 'cle').order_by('-date_action')[:10]

    # ✅ AJOUT : sociétés en essai expirant dans 3 jours (alerte)
    essai_expirant = CleActivation.objects.filter(
        statut='ACTIVE',
        type_plan='ESSAI',
        date_fin__range=(today, today + timedelta(days=3)),
    ).select_related('societe').order_by('date_fin')

    societes_sans_cle = Societe.objects.exclude(
        cles_activation__statut='ACTIVE',
        cles_activation__date_debut__lte=today,
        cles_activation__date_fin__gte=today,
    ).distinct()[:5]

    return render(request, 'superadmin/dashboard.html', {
        'stats': stats,
        'expiration_proche': expiration_proche,
        'derniers_audits': derniers_audits,
        'societes_sans_cle': societes_sans_cle,
        'essai_expirant': essai_expirant,     # ✅ AJOUT
    })


# ═══════════════════════════════════════════════════════════════
#  GESTION DES SOCIÉTÉS
# ═══════════════════════════════════════════════════════════════

@superadmin_required
def societes_liste(request):
    q = request.GET.get('q', '')
    statut = request.GET.get('statut', '')
    plan = request.GET.get('plan', '')
    today = date.today()

    societes = Societe.objects.all()

    if q:
        societes = societes.filter(Q(nom__icontains=q) | Q(nif__icontains=q))

    if statut == 'actif':
        societes = societes.filter(
            cles_activation__statut='ACTIVE',
            cles_activation__type_plan__in=['STARTER', 'BUSINESS', 'ENTERPRISE'],
            cles_activation__date_debut__lte=today,
            cles_activation__date_fin__gte=today,
        ).distinct()
    elif statut == 'essai':
        societes = societes.filter(
            cles_activation__statut='ACTIVE',
            cles_activation__type_plan='ESSAI',
            cles_activation__date_fin__gte=today,
        ).distinct()
    elif statut == 'suspendu':
        societes = societes.filter(cles_activation__statut='REVOQUEE').distinct()
    elif statut == 'inactif':
        societes = societes.exclude(cles_activation__statut__in=['ACTIVE', 'REVOQUEE']).distinct()

    if plan:
        societes = societes.filter(cles_activation__type_plan=plan.upper())

    # === PAGINATION 10 par page ===
    paginator = Paginator(societes, 10)
    page_number = request.GET.get('page')
    societes_page = paginator.get_page(page_number)

    return render(request, 'superadmin/societes_liste.html', {
        'societes': societes_page,
        'q': q,
        'statut': statut,
        'plan': plan,
        'PLANS': CleActivation.TYPE_PLAN,
        'paginator': paginator,
    })


@superadmin_required
def societe_creer(request):
    """
    Crée une société ET active automatiquement une clé d'essai 14 jours.

    LOGIQUE :
      1. Superadmin remplit les infos de base de la société (nom, NIF, adresse)
      2. La clé d'essai 14 jours est créée et activée AUTOMATIQUEMENT
      3. Le chef pourra s'inscrire via /accounts/register/ en fournissant son NIF
      4. Le système vérifiera que le NIF a une clé ACTIVE avant d'autoriser l'inscription

    Le chef ne reçoit PAS de clé — c'est le NIF qui est le "sésame" d'inscription.
    Après 14 jours, le superadmin génère une clé payante que le chef saisit dans l'appli.
    """
    if request.method == 'POST':
        form = SocieteForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                societe = form.save()

                # ── Clé essai 14j créée et activée AUTOMATIQUEMENT ──────────
                cle = CleActivation.creer_essai(societe, cree_par=request.user.username)

                # ── Journaliser ──────────────────────────────────────────────
                AuditCle.objects.create(
                    societe=societe, action='CREEE',
                    message=(
                        f"Société '{societe.nom}' (NIF: {societe.nif}) enregistrée "
                        f"par {request.user.username}."
                    ),
                    ip_address=request.META.get('REMOTE_ADDR'),
                )
                AuditCle.objects.create(
                    societe=societe, cle=cle, action='ACTIVEE',
                    message=(
                        f"Clé d'essai 14 jours activée automatiquement pour '{societe.nom}'. "
                        f"Clé: {cle.cle_visible} — expire le {cle.date_fin.strftime('%d/%m/%Y')}. "
                        f"Le chef peut s'inscrire via son NIF : {societe.nif}."
                    ),
                    ip_address=request.META.get('REMOTE_ADDR'),
                )

                messages.success(
                    request,
                    f"✅ Société « {societe.nom} » enregistrée. "
                    f"Clé d'essai 14 jours activée automatiquement (expire le "
                    f"{cle.date_fin.strftime('%d/%m/%Y')}). "
                    f"Le chef peut maintenant s'inscrire avec le NIF : {societe.nif}."
                )
                return redirect('superadmin:societe_detail', pk=societe.pk)
    else:
        form = SocieteForm()
    return render(request, 'superadmin/societe_form.html', {
        'form':  form,
        'titre': 'Enregistrer une nouvelle société',
    })


@superadmin_required
def societe_modifier(request, pk):
    societe = get_object_or_404(Societe, pk=pk)
    if request.method == 'POST':
        form = SocieteForm(request.POST, request.FILES, instance=societe)
        if form.is_valid():
            form.save()
            messages.success(request, "Société mise à jour.")
            return redirect('superadmin:societe_detail', pk=pk)
    else:
        form = SocieteForm(instance=societe)
    return render(request, 'superadmin/societe_form.html', {
        'form': form, 'titre': 'Modifier société', 'societe': societe
    })


@superadmin_required
def societe_detail(request, pk):
    """
    Fiche détaillée d'une société.

    Le superadmin peut voir :
      1. Les infos qu'il a saisies (nom + NIF) — section "Enregistrement"
      2. Les infos complétées par le chef à l'inscription — section "Informations fournies par le chef"
      3. Le compte du chef (nom, email, username, date d'inscription)
      4. Les clés d'activation (historique + active)
      5. Le journal d'audit (toutes les actions)

    Si le chef ne s'est pas encore inscrit → alerte visible.
    Si le chef s'est inscrit → comparaison possible entre ce que le superadmin
    a enregistré et ce que le chef a fourni.
    """
    societe      = get_object_or_404(Societe, pk=pk)
    cles         = societe.cles_activation.all().order_by('-date_creation')
    audits       = societe.audits.all()[:20]
    utilisateurs = Utilisateur.objects.filter(societe=societe).order_by('-date_creation')

    # ── Licence active ────────────────────────────────────────────
    licence_active = societe.cle_active   # utilise @property du modèle

    if licence_active:
        if licence_active.est_essai:
            statut_affichage = f"Essai actif — {licence_active.jours_restants} jours restants"
            statut_classe    = "warning"
        else:
            statut_affichage = f"Licence active — {licence_active.label_plan}"
            statut_classe    = "success"
    else:
        cle_revoquee = societe.cles_activation.filter(statut='REVOQUEE').exists()
        if cle_revoquee:
            statut_affichage = "Suspendu"
            statut_classe    = "danger"
        else:
            statut_affichage = "Aucune licence active"
            statut_classe    = "secondary"

    # ── Infos du chef (pour comparaison superadmin) ───────────────
    chef                 = societe.chef              # @property — DIRECTEUR lié à la société
    inscription_complete = societe.inscription_complete  # @property — chef inscrit ou non
    infos_completes      = societe.infos_completes   # @property — champs remplis par chef

    # ── Tableau comparatif : ce que le superadmin a enregistré
    #    vs ce que le chef a fourni à l'inscription ───────────────
    infos_superadmin = [
        ('NIF enregistré',        societe.nif,  'bi-fingerprint'),
        ('Date d\'enregistrement', societe.date_creation.strftime('%d/%m/%Y %H:%M'), 'bi-calendar'),
    ]

    infos_chef_societe = []
    if inscription_complete:
        infos_chef_societe = [
            ('Nom officiel fourni',  societe.nom            or '—', 'bi-building'),
            ('Registre de commerce', societe.registre      or '—', 'bi-file-earmark-text'),
            ('Téléphone',            societe.telephone     or '—', 'bi-telephone'),
            ('Boîte postale',        societe.boite_postal  or '—', 'bi-mailbox'),
            ('Centre fiscal',        societe.centre_fiscale or '—', 'bi-bank'),
            ('Assujetti TVA',        'Oui' if societe.assujeti_tva else 'Non', 'bi-receipt'),
            ('Assujetti TC',         'Oui' if societe.assujeti_tc  else 'Non', 'bi-cash-stack'),
            ('Province',             societe.province      or '—', 'bi-map'),
            ('Commune',              societe.commune       or '—', 'bi-shop'),
            ('Quartier',             societe.quartier      or '—', 'bi-geo'),
            ('Avenue',               societe.avenue        or '—', 'bi-signpost'),
            ('Numéro',               societe.numero        or '—', 'bi-hash'),
            ('Adresse complète',     societe.adresse_complete or '—', 'bi-house'),
        ]

    # ── Infos du compte chef ──────────────────────────────────────
    infos_compte_chef = []
    if chef:
        infos_compte_chef = [
            ('Nom complet',       chef.nom_complet,                                'bi-person'),
            ('Nom d\'utilisateur', chef.username,                                   'bi-person-badge'),
            ('Email',             chef.email or '—',                                'bi-envelope'),
            ('Poste',             chef.get_type_poste_display(),                    'bi-briefcase'),
            ('Date d\'inscription', chef.date_creation.strftime('%d/%m/%Y %H:%M'), 'bi-calendar-check'),
            ('Compte actif',      'Oui' if chef.actif else 'Non',                  'bi-toggle-on'),
        ]

    # ── Stats métier (si modules disponibles) ─────────────────────
    stats_societe = {}
    try:
        from clients.models import Client
        stats_societe['nb_clients'] = Client.objects.filter(societe=societe).count()
    except Exception:
        stats_societe['nb_clients'] = None

    try:
        from facturer.models import Facture
        stats_societe['nb_factures'] = Facture.objects.filter(societe=societe).count()
    except Exception:
        stats_societe['nb_factures'] = None

    return render(request, 'superadmin/societe_detail.html', {
        'societe':              societe,
        'cles':                 cles,
        'audits':               audits,
        'utilisateurs':         utilisateurs,
        'licence_active':       licence_active,
        'statut_affichage':     statut_affichage,
        'statut_classe':        statut_classe,
        'stats_societe':        stats_societe,

        # ── Infos chef & comparaison ──────────────────────────────
        'chef':                 chef,
        'inscription_complete': inscription_complete,
        'infos_completes':      infos_completes,
        'infos_superadmin':     infos_superadmin,
        'infos_chef_societe':   infos_chef_societe,
        'infos_compte_chef':    infos_compte_chef,
    })


@superadmin_required
@require_POST
def societe_toggle(request, pk):
    """
    ✅ CORRECTION : distinction suspension / réactivation.
    - Si active : suspend (révoque la clé active).
    - Si suspendue : tente de réactiver la dernière clé non-expirée.
    - Équivalent des actions suspendre_entreprise / reactiver_entreprise de PHP.
    """
    societe = get_object_or_404(Societe, pk=pk)
    today   = date.today()
    raison  = request.POST.get('raison', f"Suspendue par {request.user.username}")

    cle_active = societe.cles_activation.filter(
        statut='ACTIVE',
        date_debut__lte=today,
        date_fin__gte=today,
    ).first()

    if cle_active:
        # ── SUSPENDRE : désactiver la clé (active=False → statut=REVOQUEE) ──
        cle_active.active           = False
        cle_active.motif_revocation = raison
        cle_active.save()
        AuditCle.objects.create(
            societe=societe, cle=cle_active, action='SUSPENDUE',
            message=f"Société suspendue par {request.user.username}. Raison : {raison}",
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        messages.warning(request, f"Société « {societe.nom} » suspendue.")
    else:
        # ── RÉACTIVER : cherche la dernière clé révoquée non-expirée ──
        cle_revoquee = societe.cles_activation.filter(
            statut='REVOQUEE',
            date_fin__gte=today,
        ).order_by('-date_creation').first()

        if cle_revoquee:
            cle_revoquee.active           = True    # statut redevient ACTIVE via save()
            cle_revoquee.motif_revocation = ''
            cle_revoquee.save()
            AuditCle.objects.create(
                societe=societe, cle=cle_revoquee, action='REACTIVEE',
                message=f"Société réactivée par {request.user.username}.",
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            messages.success(
                request,
                f"Société « {societe.nom} » réactivée jusqu'au "
                f"{cle_revoquee.date_fin.strftime('%d/%m/%Y')}."
            )
        else:
            # Aucune clé réactivable → proposer une nouvelle clé
            messages.info(request, f"Générez une nouvelle clé pour réactiver « {societe.nom} ».")
            return redirect('superadmin:cle_generer', pk=pk)

    return redirect('superadmin:societe_detail', pk=pk)


@superadmin_required
@require_POST
def societe_supprimer(request, pk):
    """
    ✅ AJOUT : suppression complète d'une société avec toutes ses données.
    Équivalent de l'action supprimer_entreprise dans entreprises.php (PHP WIBABI).

    Sécurité : nécessite la saisie de "SUPPRIMER" en confirmation.
    """
    societe = get_object_or_404(Societe, pk=pk)
    confirmation = request.POST.get('confirmation', '')

    if confirmation != 'SUPPRIMER':
        messages.error(request, "Confirmation incorrecte. Tapez « SUPPRIMER » en majuscules.")
        return redirect('superadmin:societe_detail', pk=pk)

    nom_societe = societe.nom
    try:
        with transaction.atomic():
            # Les clés seront supprimées automatiquement (CASCADE depuis societe FK)
            # Pas besoin de les libérer manuellement

            # Supprimer les utilisateurs liés
            nb_users = Utilisateur.objects.filter(societe=societe).count()
            Utilisateur.objects.filter(societe=societe).delete()

            # Supprimer l'historique des connexions (cascade via utilisateurs déjà supprimés)
            # Supprimer les audits
            AuditCle.objects.filter(societe=societe).delete()

            # Tenter de supprimer les données métier si les apps existent
            _supprimer_donnees_metier(societe)

            # Supprimer la société
            societe.delete()

        messages.success(
            request,
            f"✅ Société « {nom_societe} » supprimée définitivement "
            f"({nb_users} utilisateur(s) supprimé(s))."
        )
        return redirect('superadmin:societes_liste')

    except Exception as e:
        messages.error(request, f"❌ Erreur lors de la suppression : {e}")
        return redirect('superadmin:societe_detail', pk=pk)


def _supprimer_donnees_metier(societe):
    """
    Supprime les données métier liées à la société (best-effort).
    Équivalent des DELETE en cascade dans entreprises.php de WIBABI.
    """
    modules = [
        ('facturer.models', 'LigneFacture'),
        ('facturer.models', 'Facture'),
        ('clients.models',  'Client'),
        ('clients.models',  'TypeClient'),
        ('stock.models',    'SortieStock'),
        ('stock.models',    'EntreeStock'),
        ('fournisseurs.models', 'Fournisseur'),
        ('services.models', 'Service'),
        ('produits.models', 'Produit'),
        ('categories.models', 'Categorie'),
        ('taux.models', 'Taux'),
    ]
    for module_path, model_name in modules:
        try:
            import importlib
            module = importlib.import_module(module_path)
            Model  = getattr(module, model_name)
            Model.objects.filter(societe=societe).delete()
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
#  GESTION DES CLÉS D'ACTIVATION
# ═══════════════════════════════════════════════════════════════

@superadmin_required
def cle_generer(request, pk):
    """
    ✅ CORRECTION : type_plan et duree_mois intégrés.
    Aligne sur generer_licences.php pour une société spécifique.
    """
    societe = get_object_or_404(Societe, pk=pk)
    if request.method == 'POST':
        form = CleActivationForm(request.POST)
        if form.is_valid():
            cle         = form.save(commit=False)
            cle.societe = societe
            cle.cree_par = request.user.username
            # Si type_plan est ESSAI → activer immédiatement (chef n'a pas besoin de saisir la clé)
            if cle.type_plan == 'ESSAI':
                cle.utilisee         = True
                cle.date_utilisation = timezone.now()
            cle.save()
            AuditCle.objects.create(
                societe=societe, cle=cle, action='CREEE',
                message=(
                    f"Clé {cle.cle_visible} ({cle.label_plan}) générée "
                    f"du {cle.date_debut} au {cle.date_fin} "
                    f"par {request.user.username}."
                ),
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            messages.success(request, f"✅ Clé générée : {cle.cle_visible} ({cle.label_plan})")
            return redirect('superadmin:cle_detail', pk=cle.pk)
    else:
        today        = date.today()
        dernier_jour = calendar.monthrange(today.year, today.month)[1]
        form = CleActivationForm(initial={
            'date_debut': today,
            'date_fin':   today + timedelta(days=14),  # défaut essai
            'type_plan':  'ESSAI',
        })
    return render(request, 'superadmin/cle_form.html', {'form': form, 'societe': societe})


@superadmin_required
def cle_detail(request, pk):
    cle = get_object_or_404(CleActivation, pk=pk)
    return render(request, 'superadmin/cle_detail.html', {'cle': cle})


@superadmin_required
def cle_revoquer(request, pk):
    cle = get_object_or_404(CleActivation, pk=pk)
    if request.method == 'POST':
        form = RevoquerCleForm(request.POST)
        if form.is_valid():
            motif                = form.cleaned_data['motif']
            cle.active           = False    # statut sera calculé REVOQUEE via save()
            cle.motif_revocation = motif
            cle.save()
            AuditCle.objects.create(
                societe=cle.societe, cle=cle, action='REVOQUEE',
                message=f"Révoquée par {request.user.username}. Motif: {motif}",
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            messages.warning(request, f"Clé {cle.cle_visible} révoquée.")
            if cle.societe:
                return redirect('superadmin:societe_detail', pk=cle.societe.pk)
            return redirect('superadmin:liste_cles')
    else:
        form = RevoquerCleForm()
    return render(request, 'superadmin/cle_revoquer.html', {'cle': cle, 'form': form})



@superadmin_required
def liste_cles(request):
    type_plan = request.GET.get('plan', '')
    statut = request.GET.get('statut', '')

    cles = CleActivation.objects.all().select_related('societe').order_by('-date_creation')

    if type_plan:
        cles = cles.filter(type_plan=type_plan.upper())
    if statut:
        cles = cles.filter(statut=statut.upper())

    # Pagination 10 par page
    paginator = Paginator(cles, 10)
    page_number = request.GET.get('page')
    cles_page = paginator.get_page(page_number)

    stats = {
        'total': CleActivation.objects.count(),
        'disponibles': CleActivation.objects.filter(statut='DISPONIBLE').count(),
        'actives': CleActivation.objects.filter(statut='ACTIVE').count(),
        'essai_actif': CleActivation.objects.filter(statut='ACTIVE', type_plan='ESSAI').count(),
        'expirees': CleActivation.objects.filter(statut='EXPIREE').count(),
        'revoquees': CleActivation.objects.filter(statut='REVOQUEE').count(),
    }

    return render(request, 'superadmin/liste_cles.html', {
        'cles': cles_page,
        'stats': stats,
        'PLANS': CleActivation.TYPE_PLAN,
        'filtre_plan': type_plan,
        'filtre_statut': statut,
        'paginator': paginator,
    })


    return render(request, 'superadmin/liste_cles.html', {
        'cles': cles,
        'stats': stats,
        'stats_par_plan': stats_par_plan,
        'PLANS': CleActivation.TYPE_PLAN,
        'filtre_plan': type_plan,
        'filtre_statut': statut,
    })


@superadmin_required
def creer_cle_activation(request):
    """
    Génère une clé d'activation pour une société spécifique.
    La clé intègre le nom + NIF de la société dans son code.
    Format : {NOM3}-{NIF4}-{PERIODE}-{ALEA6}  ex: SOD-4567-12M-AB3D4E
    """
    if request.method == 'POST':
        form = CleActivationForm(request.POST)
        if form.is_valid():
            cle          = form.save(commit=False)
            cle.cree_par = request.user.username
            cle.save()
            AuditCle.objects.create(
                cle=cle, societe=cle.societe, action='CREEE',
                message=(
                    f"Clé {cle.cle_visible} ({cle.label_plan}) créée pour {cle.societe.nom} "
                    f"(NIF: {cle.societe.nif}) par {request.user.username}. "
                    f"Valide du {cle.date_debut.strftime('%d/%m/%Y')} "
                    f"au {cle.date_fin.strftime('%d/%m/%Y')}."
                ),
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            messages.success(
                request,
                f"✅ Clé créée : {cle.cle_visible} ({cle.label_plan}) "
                f"pour {cle.societe.nom} — à remettre au chef."
            )
            return redirect('superadmin:liste_cles')
    else:
        today = date.today()
        form  = CleActivationForm(initial={
            'date_debut': today,
            'type_plan':  'STARTER',
        })
    return render(request, 'superadmin/creer_cle.html', {'form': form})


# ═══════════════════════════════════════════════════════════════
#  ENDPOINT AJAX — LICENCES D'UNE SOCIÉTÉ
#  ✅ AJOUT : équivalent de ajax_get_licences.php dans WIBABI
# ═══════════════════════════════════════════════════════════════

@superadmin_required
def ajax_cles_societe(request, pk):
    """
    Retourne en JSON la liste des clés d'une société.
    Appelé en AJAX depuis la page liste des sociétés (modal gérer licences).
    Équivalent exact de ajax_get_licences.php dans WIBABI PHP.
    """
    societe = get_object_or_404(Societe, pk=pk)
    cles    = societe.cles_activation.order_by('-date_activation', '-date_creation')

    data = []
    for cle in cles:
        data.append({
            'id':            cle.pk,
            'cle_visible':   cle.cle_visible,
            'type_plan':     cle.type_plan,
            'label_plan':    cle.label_plan,
            'duree_mois':    cle.duree_mois,
            'statut':        cle.statut,
            'date_creation': cle.date_creation.strftime('%Y-%m-%d %H:%M'),
            'date_activation': cle.date_activation.strftime('%Y-%m-%d %H:%M') if cle.date_activation else None,
            'date_debut':    str(cle.date_debut),
            'date_fin':      str(cle.date_fin),
            'jours_restants': cle.jours_restants,
            'est_essai':     cle.est_essai,
        })

    return JsonResponse({
        'success': True,
        'societe': societe.nom,
        'cles':    data,
        'total':   len(data),
    })


# ═══════════════════════════════════════════════════════════════
#  INSCRIPTION CHEF — Premier accès (remplace setup_complet)
#
#  LOGIQUE :
#    1. Le superadmin a déjà enregistré la société + clé essai ACTIVE
#    2. Le chef arrive sur /setup/ et remplit ses infos + les infos de sa société
#    3. Le NIF est vérifié → doit avoir une clé ACTIVE en base
#    4. Compte chef créé → connexion automatique → accueil
#    5. Pas de clé à saisir — le NIF autorisé par le superadmin suffit
# ═══════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════
#  INSCRIPTION CHEF — Version corrigée (stockage sécurisé des infos du chef)
# ═══════════════════════════════════════════════════════════════

def inscription_chef(request):
    """
    Inscription du chef de société.
    - Le chef saisit uniquement son NIF
    - On retrouve la société existante (créée par le superadmin)
    - Le chef complète les informations de la société + crée son compte DIRECTEUR
    """
    if request.user.is_authenticated:
        return redirect('accueil')

    if request.method == 'POST':
        form = InscriptionChefForm(request.POST, request.FILES)   # request.FILES pour le logo
        if form.is_valid():
            try:
                with transaction.atomic():
                    cd = form.cleaned_data
                    societe = cd.get('_societe')
                    cle_active = cd.get('_cle_active')

                    if not societe or not cle_active:
                        messages.error(request, "Erreur de validation du NIF.")
                        return render(request, 'superadmin/inscription_chef.html', {'form': form})

                    # Mise à jour des informations fournies par le CHEF
                    societe.registre          = cd.get('registre', societe.registre)
                    societe.boite_postal      = cd.get('boite_postal', societe.boite_postal)
                    societe.telephone         = cd.get('telephone', societe.telephone)
                    societe.email_societe     = cd.get('email_societe', societe.email_societe)
                    societe.province          = cd.get('province', societe.province)
                    societe.commune           = cd.get('commune', societe.commune)
                    societe.quartier          = cd.get('quartier', societe.quartier)
                    societe.avenue            = cd.get('avenue', societe.avenue)
                    societe.numero            = cd.get('numero', societe.numero)
                    societe.centre_fiscale    = cd.get('centre_fiscale', societe.centre_fiscale)
                    societe.secteur           = cd.get('secteur', societe.secteur)
                    societe.forme             = cd.get('forme', societe.forme)
                    societe.nom_complet_gerant = cd.get('nom_complet_gerant', societe.nom_complet_gerant)

                    # Booléens
                    societe.assujeti_tva = bool(cd.get('assujeti_tva', False))
                    societe.assujeti_tc  = bool(cd.get('assujeti_tc', False))
                    societe.assujeti_pfl = bool(cd.get('assujeti_pfl', False))

                    # Logo
                    if 'logo' in cd and cd['logo']:
                        societe.logo = cd['logo']

                    societe.statut = 'essai'   # Important pour éviter le modal licence
                    societe.save()

                    # Création du compte chef
                    chef = Utilisateur.objects.create_user(
                        username=cd['chef_username'],
                        password=cd['chef_password1'],
                        email=cd.get('chef_email', ''),
                        nom=cd['chef_nom'],
                        postnom=cd['chef_postnom'],
                        prenom=cd['chef_prenom'],
                        type_poste='DIRECTEUR',
                        societe=societe,
                        actif=True,
                        # Droits complets pour le directeur
                        droit_stock_categorie=True,
                        droit_stock_produit=True,
                        droit_stock_fournisseur=True,
                        droit_stock_entree=True,
                        droit_stock_sortie=True,
                        droit_facture_pnb=True,
                        droit_facture_fdnb=True,
                        droit_facture_particulier=True,
                        droit_devis=True,
                        droit_rapports=True,
                    )

                    # Activation de la clé d'essai
                    if not cle_active.utilisee:
                        cle_active.activer()

                    # Audit
                    AuditCle.objects.create(
                        societe=societe,
                        cle=cle_active,
                        action='ACTIVEE',
                        message=f"Inscription du chef {chef.nom_complet} pour la société {societe.nom}.",
                        ip_address=request.META.get('REMOTE_ADDR'),
                    )

                    # Connexion automatique
                    login(request, chef)

                    messages.success(
                        request,
                        f"✅ Bienvenue {chef.nom_complet} ! Votre société '{societe.nom}' est configurée."
                    )
                    return redirect('accueil')

            except Exception as e:
                messages.error(request, f"❌ Erreur lors de l'inscription : {str(e)}")

        # Si le formulaire a des erreurs, on passe 'societe' pour afficher le nom en lecture seule
        societe_context = getattr(form, '_societe', None) if hasattr(form, '_societe') else None

    else:
        # GET request
        form = InscriptionChefForm()
        societe_context = None

    # Rendu du template avec le contexte 'societe'
    return render(request, 'superadmin/inscription_chef.html', {
        'form': form,
        'societe': societe_context   # ← C'est cette ligne que tu demandais
    })


# ═══════════════════════════════════════════════════════════════
#  SAISIR CLÉ PAYANTE — Après expiration de l'essai 14j
#
#  LOGIQUE :
#    1. L'essai 14j expire → le middleware redirige vers /licence-expiree/
#    2. Le chef demande une licence payante au superadmin
#    3. Il reçoit une clé (ex: SOD-4567-12M-AB3D4E)
#    4. Il la saisit ici → licence prolongée → retour à l'accueil
# ═══════════════════════════════════════════════════════════════

@login_required
def saisir_cle_payante(request):
    """
    Permet au chef de saisir une clé de licence payante.

    Supporte deux modes :
      - AJAX (X-Requested-With: XMLHttpRequest) → réponse JSON
        Utilisé par le modal dans base.html
      - Normal → redirect après succès
        Utilisé depuis la page licence_expiree.html
    """
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.user.is_superuser:
        if is_ajax:
            return JsonResponse({'ok': False, 'error': 'Non autorisé pour le superadmin.'}, status=403)
        return redirect('superadmin:dashboard')

    societe = getattr(request.user, 'societe', None)
    if not societe:
        if is_ajax:
            return JsonResponse({'ok': False, 'error': 'Compte non lié à une société.'}, status=400)
        messages.error(request, "Votre compte n'est pas lié à une société.")
        return redirect(settings.LOGIN_URL)

    if request.method == 'POST':
        form = ClePayanteForm(request.POST)
        if form.is_valid():
            success, message, cle_obj = form.verifier_pour_societe(societe)
            if success:
                try:
                    with transaction.atomic():
                        cle_obj.activer()
                        AuditCle.objects.create(
                            societe    = societe,
                            cle        = cle_obj,
                            action     = 'ACTIVEE',
                            message    = (
                                f"Licence '{cle_obj.label_plan}' activée par "
                                f"'{request.user.username}' pour '{societe.nom}'. "
                                f"Valide jusqu'au {cle_obj.date_fin.strftime('%d/%m/%Y')}."
                            ),
                            ip_address = request.META.get('REMOTE_ADDR'),
                        )
                        success_msg = (
                            f"Licence {cle_obj.label_plan} activée ! "
                            f"Accès valide jusqu'au {cle_obj.date_fin.strftime('%d/%m/%Y')} "
                            f"({cle_obj.jours_restants} jours)."
                        )
                        if is_ajax:
                            return JsonResponse({'ok': True, 'message': success_msg})
                        messages.success(request, f"✅ {success_msg}")
                        return redirect('accueil')

                except Exception as e:
                    if is_ajax:
                        return JsonResponse({'ok': False, 'error': f'Erreur : {str(e)}'}, status=500)
                    messages.error(request, f"❌ Erreur lors de l'activation : {str(e)}")
            else:
                if is_ajax:
                    return JsonResponse({'ok': False, 'error': message})
                messages.error(request, f"❌ {message}")
        else:
            # Erreur de validation du formulaire
            first_error = next(iter(form.errors.values()))[0] if form.errors else 'Clé invalide.'
            if is_ajax:
                return JsonResponse({'ok': False, 'error': first_error})
            messages.error(request, first_error)
    else:
        form = ClePayanteForm()

    return render(request, 'superadmin/saisir_cle_payante.html', {
        'form':    form,
        'societe': societe,
    })


def licence_expiree(request):
    """
    Page affichée quand la licence est expirée.
    Propose deux actions :
      - Saisir une clé payante (si le chef en a une)
      - Contacter l'administrateur
    """
    societe_nom = request.session.get('licence_societe', 'Votre société')
    return render(request, 'superadmin/licence_expiree.html', {
        'societe_nom': societe_nom,
    })


# ═══════════════════════════════════════════════════════════════
#  GESTION DES UTILISATEURS
# ═══════════════════════════════════════════════════════════════

@login_required
def utilisateurs_liste(request):
    q = request.GET.get('q', '')
    poste = request.GET.get('poste', '')
    statut = request.GET.get('statut', '')

    utilisateurs = Utilisateur.objects.all().order_by('-date_creation')

    if q:
        utilisateurs = utilisateurs.filter(
            Q(nom__icontains=q) | Q(prenom__icontains=q) |
            Q(postnom__icontains=q) | Q(username__icontains=q)
        )
    if poste:
        utilisateurs = utilisateurs.filter(type_poste=poste)
    if statut == 'actif':
        utilisateurs = utilisateurs.filter(actif=True)
    elif statut == 'inactif':
        utilisateurs = utilisateurs.filter(actif=False)

    # Pagination 10 par page
    paginator = Paginator(utilisateurs, 10)
    page_number = request.GET.get('page')
    users_page = paginator.get_page(page_number)

    stats = {
        'total': Utilisateur.objects.count(),
        'actifs': Utilisateur.objects.filter(actif=True).count(),
        'inactifs': Utilisateur.objects.filter(actif=False).count(),
        'superadmins': Utilisateur.objects.filter(is_superuser=True).count(),
    }

    return render(request, 'superadmin/utilisateurs.html', {
        'utilisateurs': users_page,
        'stats': stats,
        'q': q,
        'poste': poste,
        'statut': statut,
        'types_poste': Utilisateur.TYPES_POSTE,
        'paginator': paginator,
    })

@login_required
@require_POST
def ajax_creer_utilisateur(request):
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Permission refusée'}, status=403)
    form = UtilisateurCreationForm(request.POST, request.FILES)
    if form.is_valid():
        utilisateur = form.save(commit=False)
        if hasattr(request.user, 'societe') and request.user.societe:
            utilisateur.societe = request.user.societe
        utilisateur.save()
        return JsonResponse({'success': True, 'message': f"Utilisateur {utilisateur.username} créé."})
    return JsonResponse({'success': False, 'errors': {f: e[0] for f, e in form.errors.items()}}, status=400)


@login_required
@require_POST
def ajax_modifier_utilisateur(request, pk):
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Permission refusée'}, status=403)
    utilisateur = get_object_or_404(Utilisateur, pk=pk)
    form = UtilisateurModificationForm(request.POST, request.FILES, instance=utilisateur)
    if form.is_valid():
        form.save()
        return JsonResponse({'success': True, 'message': f"{utilisateur.username} modifié."})
    return JsonResponse({'success': False, 'errors': {f: e[0] for f, e in form.errors.items()}}, status=400)


@login_required
@require_POST
def ajax_supprimer_utilisateur(request, pk):
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Permission refusée'}, status=403)
    utilisateur = get_object_or_404(Utilisateur, pk=pk)
    if utilisateur.pk == request.user.pk:
        return JsonResponse({'success': False, 'error': 'Impossible de supprimer votre propre compte.'}, status=400)
    username = utilisateur.username
    utilisateur.delete()
    return JsonResponse({'success': True, 'message': f"{username} supprimé."})


@login_required
@require_POST
def ajax_changer_mot_de_passe(request, pk):
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Permission refusée'}, status=403)
    utilisateur = get_object_or_404(Utilisateur, pk=pk)
    form = ChangerMotDePasseForm(request.POST)
    if form.is_valid():
        utilisateur.set_password(form.cleaned_data['nouveau_mot_de_passe'])
        utilisateur.save()
        return JsonResponse({'success': True, 'message': f"Mot de passe de {utilisateur.username} changé."})
    return JsonResponse({'success': False, 'errors': {f: e[0] for f, e in form.errors.items()}}, status=400)


@login_required
def ajax_info_utilisateur(request, pk):
    u = get_object_or_404(Utilisateur, pk=pk)
    return JsonResponse({
        'id': u.pk, 'nom': u.nom, 'postnom': u.postnom, 'prenom': u.prenom,
        'username': u.username, 'email': u.email or '', 'type_poste': u.type_poste,
        'actif': u.actif, 'is_superuser': u.is_superuser,
        'droit_stock_categorie': u.droit_stock_categorie,
        'droit_stock_produit': u.droit_stock_produit,
        'droit_stock_fournisseur': u.droit_stock_fournisseur,
        'droit_stock_entree': u.droit_stock_entree,
        'droit_stock_sortie': u.droit_stock_sortie,
        'droit_facture_pnb': u.droit_facture_pnb,
        'droit_facture_fdnb': u.droit_facture_fdnb,
        'droit_facture_particulier': u.droit_facture_particulier,
        'droit_devis': u.droit_devis,
        'droit_rapports': u.droit_rapports,
    })


# ═══════════════════════════════════════════════════════════════
#  BACKUP & RÉINITIALISATION
# ═══════════════════════════════════════════════════════════════

@login_required
@user_passes_test(est_superadmin)
def backup_page(request):
    backups = Backup.objects.all().order_by('-date_backup')[:20]
    return render(request, 'superadmin/backup.html', {'backups': backups})


@login_required
@user_passes_test(est_superadmin)
@require_POST
def backup_creer(request):
    try:
        backup_dir = os.path.join(settings.MEDIA_ROOT, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename  = f'backup_{timestamp}.json'
        filepath  = os.path.join(backup_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            management.call_command('dumpdata', '--indent', '2', stdout=f,
                                    exclude=['contenttypes', 'auth.permission'])
        file_size = os.path.getsize(filepath)
        backup = Backup.objects.create(
            effectue_par=request.user, type_backup='COMPLET',
            fichier=f'backups/{filename}', taille_fichier=file_size,
            succes=True, message=f"Backup créé : {file_size} octets"
        )
        messages.success(request, f"✅ Backup créé ({backup.taille_lisible})")
    except Exception as e:
        Backup.objects.create(effectue_par=request.user, type_backup='COMPLET', succes=False, message=str(e))
        messages.error(request, f"❌ Erreur : {e}")
    return redirect('superadmin:backup')


@login_required
@user_passes_test(est_superadmin)
def backup_telecharger(request, pk):
    backup = get_object_or_404(Backup, pk=pk)
    if not backup.fichier or not os.path.exists(backup.fichier.path):
        messages.error(request, "Fichier introuvable.")
        return redirect('superadmin:backup')
    return FileResponse(open(backup.fichier.path, 'rb'), as_attachment=True,
                        filename=os.path.basename(backup.fichier.path))


@login_required
@user_passes_test(est_superadmin)
def reinitialisation_page(request):
    return render(request, 'superadmin/reinitialisation.html')


@login_required
@user_passes_test(est_superadmin)
@require_POST
def reinitialisation_confirmer(request):
    if request.POST.get('confirmation', '') != 'REINITIALISER':
        messages.error(request, "Confirmation incorrecte.")
        return redirect('superadmin:reinitialisation')
    try:
        from categories.models import Categorie
        from taux.models import Taux
        from produits.models import Produit
        from services.models import Service
        from fournisseurs.models import Fournisseur
        from stock.models import EntreeStock, SortieStock
        from clients.models import Client, TypeClient
        from facturer.models import Facture, LigneFacture

        LigneFacture.objects.all().delete()
        Facture.objects.all().delete()
        Client.objects.all().delete()
        TypeClient.objects.all().delete()
        SortieStock.objects.all().delete()
        EntreeStock.objects.all().delete()
        Fournisseur.objects.all().delete()
        Service.objects.all().delete()
        Produit.objects.all().delete()
        Taux.objects.all().delete()
        Categorie.objects.all().delete()
        HistoriqueConnexion.objects.all().delete()
        Backup.objects.all().delete()

        messages.success(request, "✅ Système réinitialisé avec succès.")
        return redirect('accueil')
    except Exception as e:
        messages.error(request, f"❌ Erreur : {e}")
        return redirect('superadmin:reinitialisation')

# ═══════════════════════════════════════════════════════════════
#  GESTION DES SOCIÉTÉS (Superadmin) — Nouveau menu regroupé
# ═══════════════════════════════════════════════════════════════



@superadmin_required
def societe_gestion_liste(request):
    """
    Liste paginée des sociétés (10 par page).
    """
    societes_list = Societe.objects.all().order_by('nom')

    # Pagination : 10 sociétés par page
    paginator = Paginator(societes_list, 10)
    page_number = request.GET.get('page')
    societes = paginator.get_page(page_number)

    return render(request, 'superadmin/societe_gestion_liste.html', {
        'societes': societes,
        'page_title': 'Gestion des Sociétés',
        'paginator': paginator,   # pour afficher les numéros de pages
    })


@superadmin_required
def societe_gestion_modifier(request, pk):
    """
    Modifier les paramètres importants d'une société :
    - Nom complet du gérant
    - Email de la société
    - Numéro de départ des factures
    - Configuration OBR (username, password, system_id, actif)
    """
    societe = get_object_or_404(Societe, pk=pk)

    if request.method == 'POST':
        form     = SocieteGeranceForm(request.POST, instance=societe)
        obr_form = SocieteAdminConfigForm(request.POST, instance=societe)

        if form.is_valid() and obr_form.is_valid():
            form.save()
            obr_form.save()
            messages.success(
                request, 
                f"✅ Paramètres de la société « {societe.nom} » mis à jour avec succès."
            )
            return redirect('superadmin:societe_gestion_liste')
        
        # Si une des deux formes a des erreurs, on les affiche
        else:
            messages.error(request, "Veuillez corriger les erreurs dans le formulaire.")

    else:
        form     = SocieteGeranceForm(instance=societe)
        obr_form = SocieteAdminConfigForm(instance=societe)

    return render(request, 'superadmin/societe_gestion_form.html', {
        'form': form,
        'obr_form': obr_form,
        'societe': societe,
        'page_title': f"Modifier {societe.nom}",
    })
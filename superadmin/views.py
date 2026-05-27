# superadmin/views.py â€” VERSION FINALE
# LOGIQUE CLÃ‰S :
#   superadmin enregistre sociÃ©tÃ© â†’ clÃ© essai 14j activÃ©e AUTOMATIQUEMENT
#   le chef s'inscrit lui-mÃªme via /accounts/register/ avec son NIF
#   le NIF doit avoir une clÃ© ACTIVE sinon inscription refusÃ©e
#   aprÃ¨s 14j d'essai, superadmin gÃ©nÃ¨re une clÃ© payante â†’ chef la saisit dans l'appli

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
from facturer.models import Facture
from django.db.models import Sum
from collections import defaultdict


from .models import Utilisateur, HistoriqueConnexion, Backup, CleActivation, AuditCle
from societe.models import Societe
from stock.models import EntreeStock, SortieStock
from .forms import (
    SocieteForm, CleActivationForm, RevoquerCleForm,
    InscriptionChefForm, ClePayanteForm,
    UtilisateurCreationForm, UtilisateurModificationForm, ChangerMotDePasseForm,
    SocieteGeranceForm,          # â† Pour gÃ©rer gÃ©rant, email, numÃ©ro de dÃ©part
    SocieteAdminConfigForm,
)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  DÃ‰CORATEURS
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def superadmin_required(view_func):
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, "AccÃ¨s rÃ©servÃ© Ã  l'administrateur.")
            return redirect('accounts:login')
        return view_func(request, *args, **kwargs)
    return wrapper

def est_superadmin(user):
    return user.is_superuser


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  DASHBOARD
#  âœ… CORRECTION : stats enrichies (essai, actives, expirant)
#     AlignÃ© sur index.php de WIBABI
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


@superadmin_required
def dashboard(request):
    today = date.today()

    # Liste des sociÃ©tÃ©s pour le sÃ©lecteur
    all_societes = Societe.objects.all().order_by('nom')

    # RÃ©cupÃ©ration de la sociÃ©tÃ© sÃ©lectionnÃ©e (par dÃ©faut = premiÃ¨re sociÃ©tÃ©)
    selected_societe_id = request.GET.get('societe')
    if selected_societe_id:
        selected_societe = get_object_or_404(Societe, pk=selected_societe_id)
    else:
        selected_societe = all_societes.first() if all_societes.exists() else None

    # ==================== STATISTIQUES GLOBALES ====================
    stats = {
        'total_societes': all_societes.count(),
        'societes_actives': Societe.objects.filter(
            cles_activation__statut='ACTIVE',
            cles_activation__date_debut__lte=today,
            cles_activation__date_fin__gte=today,
        ).distinct().count(),
        'essais_actifs': Societe.objects.filter(
            cles_activation__statut='ACTIVE',
            cles_activation__type_plan='ESSAI',
            cles_activation__date_fin__gte=today,
        ).distinct().count(),
        'cles_disponibles': CleActivation.objects.filter(statut='DISPONIBLE').count(),
        'total_utilisateurs': Utilisateur.objects.count(),
    }

    # ==================== ALERTES ====================
    expiration_proche = CleActivation.objects.filter(
        statut='ACTIVE', date_fin__range=(today, today + timedelta(days=7))
    ).select_related('societe').order_by('date_fin')

    essai_expirant = CleActivation.objects.filter(
        statut='ACTIVE', type_plan='ESSAI',
        date_fin__range=(today, today + timedelta(days=3))
    ).select_related('societe').order_by('date_fin')

    societes_sans_cle = Societe.objects.exclude(
        cles_activation__statut='ACTIVE',
        cles_activation__date_debut__lte=today,
        cles_activation__date_fin__gte=today,
    ).distinct()[:5]

    derniers_audits = AuditCle.objects.select_related('societe').order_by('-date_action')[:10]

    # ==================== GRAPHique PAR SOCIÃ‰TÃ‰ ====================
    labels = []
    ca_data = []

    if selected_societe:
        start_date = today - timedelta(days=30)

        from facturer.models import Facture
        from django.db.models import Sum
        from collections import defaultdict

        factures = Facture.objects.filter(
            societe=selected_societe,
            date_facture__gte=start_date,
            statut_obr='ENVOYE'
        ).values('date_facture').annotate(
            total_ca=Sum('total_ttc')
        ).order_by('date_facture')

        ca_dict = defaultdict(int)
        for f in factures:
            ca_dict[f['date_facture']] = float(f['total_ca'] or 0)

        for i in range(30, -1, -1):
            current_date = today - timedelta(days=i)
            labels.append(current_date.strftime("%d %b"))
            ca_data.append(ca_dict[current_date])

    context = {
        'stats': stats,
        'expiration_proche': expiration_proche,
        'essai_expirant': essai_expirant,
        'societes_sans_cle': societes_sans_cle,
        'derniers_audits': derniers_audits,
        'all_societes': all_societes,
        'selected_societe': selected_societe,

        # Graphique
        'labels': labels,
        'ca_data': ca_data,
    }

    return render(request, 'superadmin/dashboard.html', context)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  GESTION DES SOCIÃ‰TÃ‰S
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

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
    CrÃ©e une sociÃ©tÃ© ET active automatiquement une clÃ© d'essai 14 jours.

    LOGIQUE :
      1. Superadmin remplit les infos de base de la sociÃ©tÃ© (nom, NIF, adresse)
      2. La clÃ© d'essai 14 jours est crÃ©Ã©e et activÃ©e AUTOMATIQUEMENT
      3. Le chef pourra s'inscrire via /accounts/register/ en fournissant son NIF
      4. Le systÃ¨me vÃ©rifiera que le NIF a une clÃ© ACTIVE avant d'autoriser l'inscription

    Le chef ne reÃ§oit PAS de clÃ© â€” c'est le NIF qui est le "sÃ©same" d'inscription.
    AprÃ¨s 14 jours, le superadmin gÃ©nÃ¨re une clÃ© payante que le chef saisit dans l'appli.
    """
    if request.method == 'POST':
        form = SocieteForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                societe = form.save()

                # â”€â”€ ClÃ© essai 14j crÃ©Ã©e et activÃ©e AUTOMATIQUEMENT â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                cle = CleActivation.creer_essai(societe, cree_par=request.user.username)

                # â”€â”€ Journaliser â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                AuditCle.objects.create(
                    societe=societe, action='CREEE',
                    message=(
                        f"SociÃ©tÃ© '{societe.nom}' (NIF: {societe.nif}) enregistrÃ©e "
                        f"par {request.user.username}."
                    ),
                    ip_address=request.META.get('REMOTE_ADDR'),
                )
                AuditCle.objects.create(
                    societe=societe, cle=cle, action='ACTIVEE',
                    message=(
                        f"ClÃ© d'essai 14 jours activÃ©e automatiquement pour '{societe.nom}'. "
                        f"ClÃ©: {cle.cle_visible} â€” expire le {cle.date_fin.strftime('%d/%m/%Y')}. "
                        f"Le chef peut s'inscrire via son NIF : {societe.nif}."
                    ),
                    ip_address=request.META.get('REMOTE_ADDR'),
                )

                messages.success(
                    request,
                    f"âœ… SociÃ©tÃ© Â« {societe.nom} Â» enregistrÃ©e. "
                    f"ClÃ© d'essai 14 jours activÃ©e automatiquement (expire le "
                    f"{cle.date_fin.strftime('%d/%m/%Y')}). "
                    f"Le chef peut maintenant s'inscrire avec le NIF : {societe.nif}."
                )
                return redirect('superadmin:societe_detail', pk=societe.pk)
    else:
        form = SocieteForm()
    return render(request, 'superadmin/societe_form.html', {
        'form':  form,
        'titre': 'Enregistrer une nouvelle sociÃ©tÃ©',
    })


@superadmin_required
def societe_modifier(request, pk):
    societe = get_object_or_404(Societe, pk=pk)
    if request.method == 'POST':
        form = SocieteForm(request.POST, request.FILES, instance=societe)
        if form.is_valid():
            form.save()
            messages.success(request, "SociÃ©tÃ© mise Ã  jour.")
            return redirect('superadmin:societe_detail', pk=pk)
    else:
        form = SocieteForm(instance=societe)
    return render(request, 'superadmin/societe_form.html', {
        'form': form, 'titre': 'Modifier sociÃ©tÃ©', 'societe': societe
    })


@superadmin_required
def societe_detail(request, pk):
    """
    Fiche dÃ©taillÃ©e d'une sociÃ©tÃ©.

    Le superadmin peut voir :
      1. Les infos qu'il a saisies (nom + NIF) â€” section "Enregistrement"
      2. Les infos complÃ©tÃ©es par le chef Ã  l'inscription â€” section "Informations fournies par le chef"
      3. Le compte du chef (nom, email, username, date d'inscription)
      4. Les clÃ©s d'activation (historique + active)
      5. Le journal d'audit (toutes les actions)

    Si le chef ne s'est pas encore inscrit â†’ alerte visible.
    Si le chef s'est inscrit â†’ comparaison possible entre ce que le superadmin
    a enregistrÃ© et ce que le chef a fourni.
    """
    societe      = get_object_or_404(Societe, pk=pk)
    cles         = societe.cles_activation.all().order_by('-date_creation')
    audits       = societe.audits.all()[:20]
    utilisateurs = Utilisateur.objects.filter(societe=societe).order_by('-date_creation')

    # â”€â”€ Licence active â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    licence_active = societe.cle_active   # utilise @property du modÃ¨le

    if licence_active:
        if licence_active.est_essai:
            statut_affichage = f"Essai actif â€” {licence_active.jours_restants} jours restants"
            statut_classe    = "warning"
        else:
            statut_affichage = f"Licence active â€” {licence_active.label_plan}"
            statut_classe    = "success"
    else:
        cle_revoquee = societe.cles_activation.filter(statut='REVOQUEE').exists()
        if cle_revoquee:
            statut_affichage = "Suspendu"
            statut_classe    = "danger"
        else:
            statut_affichage = "Aucune licence active"
            statut_classe    = "secondary"

    # â”€â”€ Infos du chef (pour comparaison superadmin) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    chef                 = societe.chef              # @property â€” DIRECTEUR liÃ© Ã  la sociÃ©tÃ©
    inscription_complete = societe.inscription_complete  # @property â€” chef inscrit ou non
    infos_completes      = societe.infos_completes   # @property â€” champs remplis par chef

    # â”€â”€ Tableau comparatif : ce que le superadmin a enregistrÃ©
    #    vs ce que le chef a fourni Ã  l'inscription â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    infos_superadmin = [
        ('NIF enregistrÃ©',        societe.nif,  'bi-fingerprint'),
        ('Date d\'enregistrement', societe.date_creation.strftime('%d/%m/%Y %H:%M'), 'bi-calendar'),
    ]

    infos_chef_societe = []
    if inscription_complete:
        infos_chef_societe = [
            ('Nom officiel fourni',  societe.nom            or 'â€”', 'bi-building'),
            ('Registre de commerce', societe.registre      or 'â€”', 'bi-file-earmark-text'),
            ('TÃ©lÃ©phone',            societe.telephone     or 'â€”', 'bi-telephone'),
            ('BoÃ®te postale',        societe.boite_postal  or 'â€”', 'bi-mailbox'),
            ('Centre fiscal',        societe.centre_fiscale or 'â€”', 'bi-bank'),
            ('Assujetti TVA',        'Oui' if societe.assujeti_tva else 'Non', 'bi-receipt'),
            ('Assujetti TC',         'Oui' if societe.assujeti_tc  else 'Non', 'bi-cash-stack'),
            ('Province',             societe.province      or 'â€”', 'bi-map'),
            ('Commune',              societe.commune       or 'â€”', 'bi-shop'),
            ('Quartier',             societe.quartier      or 'â€”', 'bi-geo'),
            ('Avenue',               societe.avenue        or 'â€”', 'bi-signpost'),
            ('NumÃ©ro',               societe.numero        or 'â€”', 'bi-hash'),
            ('Adresse complÃ¨te',     societe.adresse_complete or 'â€”', 'bi-house'),
        ]

    # â”€â”€ Infos du compte chef â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    infos_compte_chef = []
    if chef:
        infos_compte_chef = [
            ('Nom complet',       chef.nom_complet,                                'bi-person'),
            ('Nom d\'utilisateur', chef.username,                                   'bi-person-badge'),
            ('Email',             chef.email or 'â€”',                                'bi-envelope'),
            ('Poste',             chef.get_type_poste_display(),                    'bi-briefcase'),
            ('Date d\'inscription', chef.date_creation.strftime('%d/%m/%Y %H:%M'), 'bi-calendar-check'),
            ('Compte actif',      'Oui' if chef.actif else 'Non',                  'bi-toggle-on'),
        ]

    # â”€â”€ Stats mÃ©tier (si modules disponibles) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

        # â”€â”€ Infos chef & comparaison â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
    âœ… CORRECTION : distinction suspension / rÃ©activation.
    - Si active : suspend (rÃ©voque la clÃ© active).
    - Si suspendue : tente de rÃ©activer la derniÃ¨re clÃ© non-expirÃ©e.
    - Ã‰quivalent des actions suspendre_entreprise / reactiver_entreprise de PHP.
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
        # â”€â”€ SUSPENDRE : dÃ©sactiver la clÃ© (active=False â†’ statut=REVOQUEE) â”€â”€
        cle_active.active           = False
        cle_active.motif_revocation = raison
        cle_active.save()
        AuditCle.objects.create(
            societe=societe, cle=cle_active, action='SUSPENDUE',
            message=f"SociÃ©tÃ© suspendue par {request.user.username}. Raison : {raison}",
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        messages.warning(request, f"SociÃ©tÃ© Â« {societe.nom} Â» suspendue.")
    else:
        # â”€â”€ RÃ‰ACTIVER : cherche la derniÃ¨re clÃ© rÃ©voquÃ©e non-expirÃ©e â”€â”€
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
                message=f"SociÃ©tÃ© rÃ©activÃ©e par {request.user.username}.",
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            messages.success(
                request,
                f"SociÃ©tÃ© Â« {societe.nom} Â» rÃ©activÃ©e jusqu'au "
                f"{cle_revoquee.date_fin.strftime('%d/%m/%Y')}."
            )
        else:
            # Aucune clÃ© rÃ©activable â†’ proposer une nouvelle clÃ©
            messages.info(request, f"GÃ©nÃ©rez une nouvelle clÃ© pour rÃ©activer Â« {societe.nom} Â».")
            return redirect('superadmin:cle_generer', pk=pk)

    return redirect('superadmin:societe_detail', pk=pk)


@superadmin_required
@require_POST
def societe_supprimer(request, pk):
    """
    ✅ AJOUT : suppression complète d'une société avec toutes ses données.
    Sécurité : nécessite le mot de passe du superadmin en confirmation.
    """
    societe = get_object_or_404(Societe, pk=pk)
    password = request.POST.get('password', '')

    # Vérification du mot de passe superadmin
    if not request.user.check_password(password):
        messages.error(request, "Mot de passe incorrect. Suppression annulée.")
        # Redirection selon la page d'origine
        if request.META.get('HTTP_REFERER') and 'societes' in request.META.get('HTTP_REFERER'):
            return redirect('superadmin:societes_liste')
        return redirect('superadmin:societe_detail', pk=pk)

    nom_societe = societe.nom
    try:
        with transaction.atomic():
            # Les clÃ©s seront supprimÃ©es automatiquement (CASCADE depuis societe FK)
            # Pas besoin de les libÃ©rer manuellement

            # Supprimer les utilisateurs liÃ©s
            nb_users = Utilisateur.objects.filter(societe=societe).count()
            Utilisateur.objects.filter(societe=societe).delete()

            # Supprimer l'historique des connexions (cascade via utilisateurs dÃ©jÃ  supprimÃ©s)
            # Supprimer les audits
            AuditCle.objects.filter(societe=societe).delete()

            # Tenter de supprimer les donnÃ©es mÃ©tier si les apps existent
            _supprimer_donnees_metier(societe)

            # Supprimer la sociÃ©tÃ©
            societe.delete()

        messages.success(
            request,
            f"âœ… SociÃ©tÃ© Â« {nom_societe} Â» supprimÃ©e dÃ©finitivement "
            f"({nb_users} utilisateur(s) supprimÃ©(s))."
        )
        return redirect('superadmin:societes_liste')

    except Exception as e:
        messages.error(request, f"âŒ Erreur lors de la suppression : {e}")
        return redirect('superadmin:societe_detail', pk=pk)


def _supprimer_donnees_metier(societe):
    """
    Supprime les donnÃ©es mÃ©tier liÃ©es Ã  la sociÃ©tÃ© (best-effort).
    Ã‰quivalent des DELETE en cascade dans entreprises.php de WIBABI.
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


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  GESTION DES CLÃ‰S D'ACTIVATION
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

@superadmin_required
def cle_generer(request, pk):
    """
    âœ… CORRECTION : type_plan et duree_mois intÃ©grÃ©s.
    Aligne sur generer_licences.php pour une sociÃ©tÃ© spÃ©cifique.
    """
    societe = get_object_or_404(Societe, pk=pk)
    if request.method == 'POST':
        form = CleActivationForm(request.POST)
        if form.is_valid():
            cle         = form.save(commit=False)
            cle.societe = societe
            cle.cree_par = request.user.username
            # Si type_plan est ESSAI â†’ activer immÃ©diatement (chef n'a pas besoin de saisir la clÃ©)
            if cle.type_plan == 'ESSAI':
                cle.utilisee         = True
                cle.date_utilisation = timezone.now()
            cle.save()
            AuditCle.objects.create(
                societe=societe, cle=cle, action='CREEE',
                message=(
                    f"ClÃ© {cle.cle_visible} ({cle.label_plan}) gÃ©nÃ©rÃ©e "
                    f"du {cle.date_debut} au {cle.date_fin} "
                    f"par {request.user.username}."
                ),
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            messages.success(request, f"âœ… ClÃ© gÃ©nÃ©rÃ©e : {cle.cle_visible} ({cle.label_plan})")
            return redirect('superadmin:cle_detail', pk=cle.pk)
    else:
        today        = date.today()
        dernier_jour = calendar.monthrange(today.year, today.month)[1]
        form = CleActivationForm(initial={
            'date_debut': today,
            'date_fin':   today + timedelta(days=14),  # dÃ©faut essai
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
            cle.active           = False    # statut sera calculÃ© REVOQUEE via save()
            cle.motif_revocation = motif
            cle.save()
            AuditCle.objects.create(
                societe=cle.societe, cle=cle, action='REVOQUEE',
                message=f"RÃ©voquÃ©e par {request.user.username}. Motif: {motif}",
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            messages.warning(request, f"ClÃ© {cle.cle_visible} rÃ©voquÃ©e.")
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
    GÃ©nÃ¨re une clÃ© d'activation pour une sociÃ©tÃ© spÃ©cifique.
    La clÃ© intÃ¨gre le nom + NIF de la sociÃ©tÃ© dans son code.
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
                    f"ClÃ© {cle.cle_visible} ({cle.label_plan}) crÃ©Ã©e pour {cle.societe.nom} "
                    f"(NIF: {cle.societe.nif}) par {request.user.username}. "
                    f"Valide du {cle.date_debut.strftime('%d/%m/%Y')} "
                    f"au {cle.date_fin.strftime('%d/%m/%Y')}."
                ),
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            messages.success(
                request,
                f"âœ… ClÃ© crÃ©Ã©e : {cle.cle_visible} ({cle.label_plan}) "
                f"pour {cle.societe.nom} â€” Ã  remettre au chef."
            )
            return redirect('superadmin:liste_cles')
    else:
        today = date.today()
        form  = CleActivationForm(initial={
            'date_debut': today,
            'type_plan':  'STARTER',
        })
    return render(request, 'superadmin/creer_cle.html', {'form': form})


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  ENDPOINT AJAX â€” LICENCES D'UNE SOCIÃ‰TÃ‰
#  âœ… AJOUT : Ã©quivalent de ajax_get_licences.php dans WIBABI
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

@superadmin_required
def ajax_cles_societe(request, pk):
    """
    Retourne en JSON la liste des clÃ©s d'une sociÃ©tÃ©.
    AppelÃ© en AJAX depuis la page liste des sociÃ©tÃ©s (modal gÃ©rer licences).
    Ã‰quivalent exact de ajax_get_licences.php dans WIBABI PHP.
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


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  INSCRIPTION CHEF â€” Premier accÃ¨s (remplace setup_complet)
#
#  LOGIQUE :
#    1. Le superadmin a dÃ©jÃ  enregistrÃ© la sociÃ©tÃ© + clÃ© essai ACTIVE
#    2. Le chef arrive sur /setup/ et remplit ses infos + les infos de sa sociÃ©tÃ©
#    3. Le NIF est vÃ©rifiÃ© â†’ doit avoir une clÃ© ACTIVE en base
#    4. Compte chef crÃ©Ã© â†’ connexion automatique â†’ accueil
#    5. Pas de clÃ© Ã  saisir â€” le NIF autorisÃ© par le superadmin suffit
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  INSCRIPTION CHEF â€” Version corrigÃ©e (stockage sÃ©curisÃ© des infos du chef)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def inscription_chef(request):
    """
    Inscription du chef de sociÃ©tÃ©.
    - Le chef saisit uniquement son NIF
    - On retrouve la sociÃ©tÃ© existante (crÃ©Ã©e par le superadmin)
    - Le chef complÃ¨te les informations de la sociÃ©tÃ© + crÃ©e son compte DIRECTEUR
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

                    # Mise Ã  jour des informations fournies par le CHEF
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

                    # BoolÃ©ens
                    societe.assujeti_tva = bool(cd.get('assujeti_tva', False))
                    societe.assujeti_tc  = bool(cd.get('assujeti_tc', False))
                    societe.assujeti_pfl = bool(cd.get('assujeti_pfl', False))

                    # Logo
                    if 'logo' in cd and cd['logo']:
                        societe.logo = cd['logo']

                    societe.statut = 'essai'   # Important pour Ã©viter le modal licence
                    societe.save()

                    # CrÃ©ation du compte chef
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
                        message=f"Inscription du contribuable {chef.nom_complet} pour la société {societe.nom}.",
                        ip_address=request.META.get('REMOTE_ADDR'),
                    )

                    # Connexion automatique
                    login(request, chef)

                    messages.success(
                        request,
                        f"âœ… Bienvenue {chef.nom_complet} ! Votre sociÃ©tÃ© '{societe.nom}' est configurÃ©e."
                    )
                    return redirect('accueil')

            except Exception as e:
                messages.error(request, f"âŒ Erreur lors de l'inscription : {str(e)}")

        # Si le formulaire a des erreurs, on passe 'societe' pour afficher le nom en lecture seule
        societe_context = getattr(form, '_societe', None) if hasattr(form, '_societe') else None

    else:
        # GET request
        form = InscriptionChefForm()
        societe_context = None

    # Rendu du template avec le contexte 'societe'
    return render(request, 'superadmin/inscription_chef.html', {
        'form': form,
        'societe': societe_context   # â† C'est cette ligne que tu demandais
    })


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  SAISIR CLÃ‰ PAYANTE â€” AprÃ¨s expiration de l'essai 14j
#
#  LOGIQUE :
#    1. L'essai 14j expire â†’ le middleware redirige vers /licence-expiree/
#    2. Le chef demande une licence payante au superadmin
#    3. Il reÃ§oit une clÃ© (ex: SOD-4567-12M-AB3D4E)
#    4. Il la saisit ici â†’ licence prolongÃ©e â†’ retour Ã  l'accueil
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

@login_required
def saisir_cle_payante(request):
    societe = getattr(request.user, 'societe', None)
    if not societe:
        messages.error(request, "Votre compte n'est pas liÃ© Ã  une sociÃ©tÃ©.")
        return redirect('accueil')

    if request.method == 'POST':
        print("=== POST REÃ‡U ===")                    # â† Debug 1
        print("DonnÃ©es POST :", request.POST)         # â† Debug 2
        
        form = ClePayanteForm(request.POST)
        
        if form.is_valid():
            print("Formulaire valide")                 # â† Debug 3
            success, message, cle_obj = form.verifier_pour_societe(societe)
            
            print(f"Success: {success} | Message: {message}")   # â† Debug 4
            
            if success and cle_obj:
                cle_obj.activer()
                messages.success(request, f"âœ… Licence activÃ©e avec succÃ¨s !")
                return redirect('accueil')
            else:
                messages.error(request, message or "ClÃ© invalide")
        else:
            print("Erreurs formulaire :", form.errors)   # â† Debug 5
            messages.error(request, "Veuillez vÃ©rifier la clÃ© saisie.")

    else:
        form = ClePayanteForm()

    return render(request, 'superadmin/saisir_cle_payante.html', {
        'form': form,
        'societe': societe,
    })

def licence_expiree(request):
    """
    Page affichÃ©e quand la licence est expirÃ©e.
    Propose deux actions :
      - Saisir une clÃ© payante (si le chef en a une)
      - Contacter l'administrateur
    """
    societe_nom = request.session.get('licence_societe', 'Votre sociÃ©tÃ©')
    return render(request, 'superadmin/licence_expiree.html', {
        'societe_nom': societe_nom,
    })


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  GESTION DES UTILISATEURS
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

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
        return JsonResponse({'success': False, 'error': 'Permission refusÃ©e'}, status=403)
    form = UtilisateurCreationForm(request.POST, request.FILES)
    if form.is_valid():
        utilisateur = form.save(commit=False)
        if hasattr(request.user, 'societe') and request.user.societe:
            utilisateur.societe = request.user.societe
        utilisateur.save()
        return JsonResponse({'success': True, 'message': f"Utilisateur {utilisateur.username} crÃ©Ã©."})
    return JsonResponse({'success': False, 'errors': {f: e[0] for f, e in form.errors.items()}}, status=400)


@login_required
@require_POST
def ajax_modifier_utilisateur(request, pk):
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Permission refusÃ©e'}, status=403)
    utilisateur = get_object_or_404(Utilisateur, pk=pk)
    form = UtilisateurModificationForm(request.POST, request.FILES, instance=utilisateur)
    if form.is_valid():
        form.save()
        return JsonResponse({'success': True, 'message': f"{utilisateur.username} modifiÃ©."})
    return JsonResponse({'success': False, 'errors': {f: e[0] for f, e in form.errors.items()}}, status=400)


@login_required
@require_POST
def ajax_supprimer_utilisateur(request, pk):
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Permission refusÃ©e'}, status=403)
    utilisateur = get_object_or_404(Utilisateur, pk=pk)
    if utilisateur.pk == request.user.pk:
        return JsonResponse({'success': False, 'error': 'Impossible de supprimer votre propre compte.'}, status=400)
    username = utilisateur.username
    utilisateur.delete()
    return JsonResponse({'success': True, 'message': f"{username} supprimÃ©."})


@login_required
@require_POST
def ajax_changer_mot_de_passe(request, pk):
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Permission refusÃ©e'}, status=403)
    utilisateur = get_object_or_404(Utilisateur, pk=pk)
    form = ChangerMotDePasseForm(request.POST)
    if form.is_valid():
        utilisateur.set_password(form.cleaned_data['nouveau_mot_de_passe'])
        utilisateur.save()
        return JsonResponse({'success': True, 'message': f"Mot de passe de {utilisateur.username} changÃ©."})
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


# ————————————————————————————————————————————————————————————————————————————————————————————————————
#  BACKUP & RÉINITIALISATION
# ————————————————————————————————————————————————————————————————————————————————————————————————————

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

#  GESTION DES SOCIÃ‰TÃ‰S (Superadmin) â€” Nouveau menu regroupÃ©
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•



@superadmin_required
def societe_gestion_liste(request):
    """
    Liste paginÃ©e des sociÃ©tÃ©s (10 par page).
    """
    societes_list = Societe.objects.all().order_by('nom')

    # Pagination : 10 sociÃ©tÃ©s par page
    paginator = Paginator(societes_list, 10)
    page_number = request.GET.get('page')
    societes = paginator.get_page(page_number)

    return render(request, 'superadmin/societe_gestion_liste.html', {
        'societes': societes,
        'page_title': 'Gestion des SociÃ©tÃ©s',
        'paginator': paginator,   # pour afficher les numÃ©ros de pages
    })


@superadmin_required
def societe_gestion_modifier(request, pk):
    societe = get_object_or_404(Societe, pk=pk)

    if request.method == 'POST':
        print("=== POST brut ===")
        print("obr_password reÃ§u:", repr(request.POST.get('obr_password')))

        form     = SocieteGeranceForm(request.POST, instance=societe)
        obr_form = SocieteAdminConfigForm(request.POST, instance=societe)

        print("obr_form valid:", obr_form.is_valid())
        print("obr_form errors:", obr_form.errors)
        if obr_form.is_valid():
            print("obr_password cleaned:", repr(obr_form.cleaned_data.get('obr_password')))

        if form.is_valid() and obr_form.is_valid():
            with transaction.atomic():
                gerance = form.save(commit=False)
                obr     = obr_form.save(commit=False)

                societe.nom_complet_gerant = gerance.nom_complet_gerant
                societe.email_societe      = gerance.email_societe
                societe.numero_depart      = gerance.numero_depart
                societe.obr_actif          = obr.obr_actif
                societe.obr_username       = obr.obr_username
                societe.obr_system_id      = obr.obr_system_id
                societe.obr_base_url       = obr.obr_base_url
                societe.obr_password       = obr.obr_password

                print("=== AVANT SAVE ===")
                print("societe.obr_password:", repr(societe.obr_password))

                societe.save()

                print("=== APRÃˆS SAVE ===")
                societe.refresh_from_db()
                print("obr_password en base:", repr(societe.obr_password))

            messages.success(request, f"âœ… ParamÃ¨tres de Â« {societe.nom} Â» mis Ã  jour.")
            return redirect('superadmin:societe_gestion_liste')
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")

    else:
        form     = SocieteGeranceForm(instance=societe)
        obr_form = SocieteAdminConfigForm(instance=societe)
    return render(request, 'superadmin/societe_gestion_form.html', {
        'form': form,
        'obr_form': obr_form,
        'societe': societe,
        'page_title': f"Modifier les paramètres de {societe.nom}",
    })


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  SUIVI GLOBAL DES STOCKS (Transactions)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

@superadmin_required
def stock_entrees(request):
    """Liste globale des entrées stock, groupée par société."""
    q        = request.GET.get('q', '')
    statut   = request.GET.get('statut', '')
    type_mvt = request.GET.get('type', '')
    societe_id = request.GET.get('societe', '')
    page_num = request.GET.get('page', 1)

    entrees_all = EntreeStock.objects.all().select_related('produit', 'societe')

    if q:
        entrees_all = entrees_all.filter(
            Q(produit__designation__icontains=q) |
            Q(produit__code__icontains=q) |
            Q(numero_ref__icontains=q)
        )
    if statut:
        entrees_all = entrees_all.filter(statut_obr=statut)
    if type_mvt:
        entrees_all = entrees_all.filter(type_entree=type_mvt)
    if societe_id:
        entrees_all = entrees_all.filter(societe_id=societe_id)

    stats = {
        'total': entrees_all.count(),
        'en_attente': entrees_all.filter(statut_obr='EN_ATTENTE').count(),
        'envoyes': entrees_all.filter(statut_obr='ENVOYE').count(),
    }

    societes_list = Societe.objects.filter(entrees_stock__in=entrees_all).distinct().order_by('nom')
    paginator = Paginator(societes_list, 10)
    page_obj = paginator.get_page(page_num)

    grouped_data = []
    for s in page_obj:
        grouped_data.append({
            'societe': s,
            'entrees': entrees_all.filter(societe=s).order_by('-date_creation')
        })

    return render(request, 'superadmin/stock_entrees.html', {
        'grouped_data': grouped_data,
        'page_obj': page_obj,
        'stats': stats,
        'q': q,
        'statut': statut,
        'type_mvt': type_mvt,
        'societe_id': societe_id,
        'societes': Societe.objects.all().order_by('nom'),
        'types': EntreeStock.TYPE_ENTREE_CHOICES,
        'statuts': EntreeStock.STATUT_OBR_CHOICES,
    })


@superadmin_required
def stock_sorties(request):
    """Liste globale des sorties stock, groupée par société."""
    q        = request.GET.get('q', '')
    statut   = request.GET.get('statut', '')
    type_mvt = request.GET.get('type', '')
    societe_id = request.GET.get('societe', '')
    page_num = request.GET.get('page', 1)

    sorties_all = SortieStock.objects.all().select_related('entree_stock__produit', 'societe')

    if q:
        sorties_all = sorties_all.filter(
            Q(entree_stock__produit__designation__icontains=q) |
            Q(entree_stock__produit__code__icontains=q) |
            Q(code__icontains=q)
        )
    if statut:
        sorties_all = sorties_all.filter(statut_obr=statut)
    if type_mvt:
        sorties_all = sorties_all.filter(type_sortie=type_mvt)
    if societe_id:
        sorties_all = sorties_all.filter(societe_id=societe_id)

    stats = {
        'total': sorties_all.count(),
        'en_attente': sorties_all.filter(statut_obr='EN_ATTENTE').count(),
        'envoyes': sorties_all.filter(statut_obr='ENVOYE').count(),
    }

    societes_list = Societe.objects.filter(sorties_stock__in=sorties_all).distinct().order_by('nom')
    paginator = Paginator(societes_list, 10)
    page_obj = paginator.get_page(page_num)

    grouped_data = []
    for s in page_obj:
        grouped_data.append({
            'societe': s,
            'sorties': sorties_all.filter(societe=s).order_by('-date_creation')
        })

    return render(request, 'superadmin/stock_sorties.html', {
        'grouped_data': grouped_data,
        'page_obj': page_obj,
        'stats': stats,
        'q': q,
        'statut': statut,
        'type_mvt': type_mvt,
        'societe_id': societe_id,
        'societes': Societe.objects.all().order_by('nom'),
        'types': SortieStock.TYPE_SORTIE_CHOICES,
        'statuts': SortieStock.STATUT_OBR_CHOICES,
    })

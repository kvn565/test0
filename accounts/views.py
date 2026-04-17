# accounts/views.py

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone

from .forms import ConnexionForm, ProfilForm, MotDePasseForm
from superadmin.models import Utilisateur, HistoriqueConnexion


# ─────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────

def _get_ip(request):
    return (
        request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
        or request.META.get('REMOTE_ADDR', '')
    )


def _get_statut_societe(societe):
    """
    Retourne le statut actuel de la société basé sur ses clés d'activation.

    ✅ CORRIGÉ : timezone.now() au lieu de date.today()
       → Les champs date_debut / date_fin sont des DateTimeField
       → Utiliser timezone.now() évite les bugs de comparaison datetime/date

    Retourne : (statut: str, cle: CleActivation|None)
    """
    now = timezone.now()   # ✅ CORRIGÉ (était date.today())

    # Clé actuellement active
    cle_active = societe.cles_activation.filter(
        statut='ACTIVE',
        date_debut__lte=now,
        date_fin__gte=now,
    ).first()

    if cle_active:
        if cle_active.type_plan == 'ESSAI':
            return 'essai_actif', cle_active
        return 'actif', cle_active

    # Clé révoquée → compte suspendu
    if societe.cles_activation.filter(statut='REVOQUEE').exists():
        return 'suspendu', None

    # Clé expirée (date_fin dépassée) → laisser le middleware et le modal gérer
    if societe.cles_activation.filter(statut='ACTIVE', date_fin__lt=now).exists():
        return 'essai_expire', None

    # Aucune clé → en attente (edge case dans le nouveau flow)
    if societe.cles_activation.filter(statut='DISPONIBLE').exists():
        return 'en_attente', None

    return 'inactif', None


# ─────────────────────────────────────────────────────────────────
#  LOGIN
# ─────────────────────────────────────────────────────────────────

def login_view(request):
    """
    Connexion utilisateur.

    FLOW SIMPLIFIÉ vs ancienne version :
    - Licence expirée → on redirige vers 'accueil', le LicenceMiddleware
      intercepte et redirige vers /licence-expiree/ où le modal s'ouvre.
    - Seuls 'suspendu', 'en_attente' et 'inactif' ont une page dédiée
      car ce ne sont pas des cas gérés par le modal (pas de clé à saisir).
    """
    if request.user.is_authenticated:
        if request.user.is_superuser:
            return redirect('superadmin:dashboard')
        return redirect('accueil')

    form = ConnexionForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        username = form.cleaned_data['username']
        password = form.cleaned_data['password']
        remember = form.cleaned_data.get('remember', False)
        ip       = _get_ip(request)

        user = authenticate(request, username=username, password=password)

        if user is not None:

            # ── Compte désactivé ─────────────────────────────────
            if not user.actif:
                form.add_error(None, "Votre compte a été désactivé. Contactez l'administrateur.")
                _log_connexion(user, ip, request)
                return render(request, 'accounts/login.html', {'form': form})

            # ── Superadmin → accès direct ─────────────────────────
            if user.is_superuser:
                login(request, user)
                _log_connexion(user, ip, request)
                _set_session_expiry(request, remember)
                return redirect('superadmin:dashboard')

            # ── Utilisateur normal → vérifier la société ──────────
            if not user.societe:
                form.add_error(None, "Aucune société associée à votre compte.")
                return render(request, 'accounts/login.html', {'form': form})

            statut, _ = _get_statut_societe(user.societe)

            login(request, user)
            _log_connexion(user, ip, request)
            _set_session_expiry(request, remember)
            user.save(update_fields=['last_login'])

            # ── Redirection selon statut ──────────────────────────
            if statut == 'suspendu':
                # Clé révoquée → page d'information claire
                return redirect('accounts:suspendu')

            elif statut in ('en_attente', 'inactif'):
                # Aucune clé → en attente ou inactif
                # (rare dans le nouveau flow : superadmin crée toujours un essai)
                return redirect('accounts:attente')

            else:
                # actif, essai_actif, essai_expire → vers accueil
                # Le LicenceMiddleware gère l'expiration et redirige vers /licence-expiree/
                # Le modal dans base.html prend le relais pour la saisie de clé
                return redirect('accueil')

        else:
            # ── Identifiants incorrects ───────────────────────────
            try:
                user_echec = Utilisateur.objects.get(username=username)
                _log_connexion(user_echec, ip, request)
            except Utilisateur.DoesNotExist:
                pass
            form.add_error(None, "Identifiants incorrects.")

    return render(request, 'accounts/login.html', {'form': form})


def _log_connexion(user, ip, request):
    """Enregistre une tentative de connexion dans l'historique."""
    try:
        HistoriqueConnexion.objects.create(
            utilisateur=user,
            adresse_ip=ip,
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )
    except Exception:
        pass


def _set_session_expiry(request, remember):
    """Gère 'Se souvenir de moi' → session longue ou fermeture navigateur."""
    if remember:
        request.session.set_expiry(60 * 60 * 24 * 30)  # 30 jours
    else:
        request.session.set_expiry(0)  # Expire à la fermeture du navigateur


# ─────────────────────────────────────────────────────────────────
#  LOGOUT
# ─────────────────────────────────────────────────────────────────

def logout_view(request):
    """Déconnexion — termine la session et marque la déconnexion dans l'historique."""
    if request.user.is_authenticated:
        try:
            conn = HistoriqueConnexion.objects.filter(
                utilisateur=request.user,
                date_deconnexion__isnull=True,
            ).order_by('-date_connexion').first()
            if conn:
                conn.terminer_session()
        except Exception:
            pass
    logout(request)
    return redirect('accounts:login')


# ─────────────────────────────────────────────────────────────────
#  PROFIL
#  ✅ AJOUTÉ : base.html référence {% url 'accounts:profil' %}
# ─────────────────────────────────────────────────────────────────

@login_required
def profil_view(request):
    """
    Page profil : modifier infos personnelles + changer de mot de passe.
    Deux formulaires indépendants sur la même page.
    """
    profil_form = ProfilForm(instance=request.user)
    mdp_form    = MotDePasseForm(user=request.user)

    if request.method == 'POST':

        if 'changer_profil' in request.POST:
            profil_form = ProfilForm(request.POST, instance=request.user)
            if profil_form.is_valid():
                profil_form.save()
                messages.success(request, "✅ Informations mises à jour avec succès.")
                return redirect('accounts:profil')

        elif 'changer_mdp' in request.POST:
            mdp_form = MotDePasseForm(user=request.user, data=request.POST)
            if mdp_form.is_valid():
                mdp_form.save()
                # Maintenir la session après changement de mot de passe
                update_session_auth_hash(request, request.user)
                messages.success(request, "✅ Mot de passe modifié avec succès.")
                return redirect('accounts:profil')

    return render(request, 'accounts/profil.html', {
        'profil_form': profil_form,
        'mdp_form':    mdp_form,
    })


# ─────────────────────────────────────────────────────────────────
#  ACCUEIL
# ─────────────────────────────────────────────────────────────────

@login_required
def accueil_view(request):
    """
    Accueil principal après connexion.
    Le LicenceMiddleware s'assure que seuls les utilisateurs avec
    une licence valide atteignent cette vue.
    """
    return render(request, 'accueil.html')


# ─────────────────────────────────────────────────────────────────
#  PAGES D'ÉTAT — Cas bloquants sans solution de saisie de clé
# ─────────────────────────────────────────────────────────────────

@login_required
def attente_view(request):
    """
    Société en attente d'attribution de licence.
    Cas rare dans le nouveau flow (superadmin crée toujours un essai auto).
    Affiché aussi pour les sociétés 'inactif'.
    """
    return render(request, 'accounts/attente.html', {
        'societe': request.user.societe,
    })


@login_required
def inactif_view(request):
    """Société inactive — aucune clé jamais attribuée."""
    return render(request, 'accounts/inactif.html', {
        'societe': request.user.societe,
    })


@login_required
def suspendu_view(request):
    """
    Clé révoquée par l'administrateur.
    Différent de 'expiré' : la révocation est volontaire et l'utilisateur
    ne peut PAS se débloquer lui-même avec une clé — contacter l'admin.
    """
    return render(request, 'accounts/suspendu.html', {
        'societe': request.user.societe,
    })


# ─────────────────────────────────────────────────────────────────
#  SUPPRIMÉ : setup_view
# ─────────────────────────────────────────────────────────────────
#
#  L'ancien setup_view (SetupActivationForm avec clé + NIF) est remplacé
#  par superadmin.views.inscription_chef, accessible sur /setup/.
#  L'URL /setup/ est définie dans le urls.py principal du projet.
#
# ─────────────────────────────────────────────────────────────────
#  SUPPRIMÉ : activer_licence_view
# ─────────────────────────────────────────────────────────────────
#
#  L'activation de licence est maintenant gérée par :
#  1. LicenceMiddleware → détecte expiration → redirect /licence-expiree/
#  2. Modal AJAX dans base.html → POST vers superadmin:saisir_cle
#  3. Page superadmin/licence_expiree.html avec bouton "J'ai ma clé"

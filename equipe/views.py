# equipe/views.py
# Gestion de l'équipe par le Directeur (chef de société)
# Le chef peut : créer, modifier, supprimer les employés de SA société
# Le chef ne peut PAS : modifier un autre DIRECTEUR, se supprimer lui-même, créer un superuser

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from superadmin.models import Utilisateur


# ── Décorateur : chef de société uniquement ───────────────────
def chef_required(view_func):
    """Accessible uniquement au Directeur d'une société (non superadmin)."""
    from functools import wraps
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        u = request.user
        if not u.is_authenticated:
            from django.shortcuts import redirect
            return redirect('accounts:login')
        if u.is_superuser or u.type_poste != 'DIRECTEUR' or not u.societe:
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden("Accès réservé au Directeur.")
        return view_func(request, *args, **kwargs)
    return wrapper


# ══════════════════════════════════════════════════════════════
#  PAGE PRINCIPALE — LISTE DE L'ÉQUIPE
# ══════════════════════════════════════════════════════════════
@login_required
@chef_required
def liste_equipe(request):
    """Affiche tous les employés de la société du chef connecté."""
    employes = (
        Utilisateur.objects
        .filter(societe=request.user.societe, is_superuser=False)
        .exclude(pk=request.user.pk)          # le chef lui-même n'apparaît pas
        .order_by('nom', 'prenom')
    )
    types_poste = [
        tp for tp in Utilisateur.TYPES_POSTE
        if tp[0] != 'DIRECTEUR'               # le chef ne peut pas créer un autre directeur
    ]
    return render(request, 'equipe/equipe.html', {
        'employes':    employes,
        'types_poste': types_poste,
        'societe':     request.user.societe,
    })


# ══════════════════════════════════════════════════════════════
#  AJAX — CRÉER UN EMPLOYÉ
# ══════════════════════════════════════════════════════════════
@login_required
@chef_required
@require_POST
def ajax_creer_employe(request):
    data = request.POST

    # Validation des champs obligatoires
    required = ['nom', 'postnom', 'prenom', 'username', 'password', 'type_poste']
    for field in required:
        if not data.get(field, '').strip():
            return JsonResponse({'success': False, 'error': f"Le champ '{field}' est obligatoire."}, status=400)

    if data['type_poste'] == 'DIRECTEUR':
        return JsonResponse({'success': False, 'error': "Vous ne pouvez pas créer un autre Directeur."}, status=400)

    if Utilisateur.objects.filter(username=data['username'].strip()).exists():
        return JsonResponse({'success': False, 'error': "Ce nom d'utilisateur est déjà pris."}, status=400)

    # Validation du mot de passe
    try:
        validate_password(data['password'])
    except ValidationError as e:
        return JsonResponse({'success': False, 'error': ' '.join(e.messages)}, status=400)

    employe = Utilisateur(
        nom        = data['nom'].strip().upper(),
        postnom    = data['postnom'].strip().upper(),
        prenom     = data['prenom'].strip().capitalize(),
        username   = data['username'].strip().lower(),
        email      = data.get('email', '').strip() or '',
        type_poste = data['type_poste'],
        societe    = request.user.societe,
        actif      = True,
        is_superuser = False,
        is_staff     = False,
    )
    employe.set_password(data['password'])

    # Appliquer les droits cochés
    _appliquer_droits(employe, data)
    employe.save()

    return JsonResponse({
        'success': True,
        'message': f"Employé {employe.nom_complet} créé avec succès.",
        'employe': _employe_dict(employe),
    })


# ══════════════════════════════════════════════════════════════
#  AJAX — MODIFIER LES DROITS D'UN EMPLOYÉ
# ══════════════════════════════════════════════════════════════
@login_required
@chef_required
@require_POST
def ajax_modifier_employe(request, pk):
    employe = get_object_or_404(Utilisateur, pk=pk, societe=request.user.societe)

    # Sécurité : ne peut pas modifier un autre directeur ou superuser
    if employe.is_superuser or employe.type_poste == 'DIRECTEUR':
        return JsonResponse({'success': False, 'error': "Action non autorisée sur ce compte."}, status=403)

    data = request.POST

    # Infos de base
    if data.get('nom'):        employe.nom        = data['nom'].strip().upper()
    if data.get('postnom'):    employe.postnom    = data['postnom'].strip().upper()
    if data.get('prenom'):     employe.prenom     = data['prenom'].strip().capitalize()
    if data.get('type_poste') and data['type_poste'] != 'DIRECTEUR':
        employe.type_poste = data['type_poste']
    if 'email' in data:        employe.email      = data['email'].strip()
    if 'actif' in data:        employe.actif      = data['actif'] == '1'

    # Appliquer les droits
    _appliquer_droits(employe, data)
    employe.save()

    return JsonResponse({
        'success': True,
        'message': f"Droits de {employe.nom_complet} mis à jour.",
        'employe': _employe_dict(employe),
    })


# ══════════════════════════════════════════════════════════════
#  AJAX — CHANGER LE MOT DE PASSE D'UN EMPLOYÉ
# ══════════════════════════════════════════════════════════════
@login_required
@chef_required
@require_POST
def ajax_changer_mdp_employe(request, pk):
    employe = get_object_or_404(Utilisateur, pk=pk, societe=request.user.societe)

    if employe.is_superuser or employe.type_poste == 'DIRECTEUR':
        return JsonResponse({'success': False, 'error': "Action non autorisée."}, status=403)

    nouveau_mdp = request.POST.get('nouveau_mot_de_passe', '').strip()
    if not nouveau_mdp:
        return JsonResponse({'success': False, 'error': "Le mot de passe ne peut pas être vide."}, status=400)

    try:
        validate_password(nouveau_mdp, user=employe)
    except ValidationError as e:
        return JsonResponse({'success': False, 'error': ' '.join(e.messages)}, status=400)

    employe.set_password(nouveau_mdp)
    employe.save()

    return JsonResponse({'success': True, 'message': f"Mot de passe de {employe.nom_complet} modifié."})


# ══════════════════════════════════════════════════════════════
#  AJAX — SUPPRIMER UN EMPLOYÉ
# ══════════════════════════════════════════════════════════════
@login_required
@chef_required
@require_POST
def ajax_supprimer_employe(request, pk):
    employe = get_object_or_404(Utilisateur, pk=pk, societe=request.user.societe)

    if employe.is_superuser or employe.type_poste == 'DIRECTEUR':
        return JsonResponse({'success': False, 'error': "Action non autorisée."}, status=403)
    if employe.pk == request.user.pk:
        return JsonResponse({'success': False, 'error': "Vous ne pouvez pas supprimer votre propre compte."}, status=400)

    nom = employe.nom_complet
    employe.delete()
    return JsonResponse({'success': True, 'message': f"{nom} supprimé."})


# ══════════════════════════════════════════════════════════════
#  AJAX — INFO D'UN EMPLOYÉ (pour pré-remplir le modal)
# ══════════════════════════════════════════════════════════════
@login_required
@chef_required
def ajax_info_employe(request, pk):
    employe = get_object_or_404(Utilisateur, pk=pk, societe=request.user.societe)
    return JsonResponse(_employe_dict(employe))


# ══════════════════════════════════════════════════════════════
#  HELPERS PRIVÉS
# ══════════════════════════════════════════════════════════════
DROITS = [
    'droit_stock_categorie',
    'droit_stock_produit',
    'droit_stock_fournisseur',
    'droit_stock_entree',
    'droit_stock_sortie',
    'droit_facture_pnb',
    'droit_facture_fdnb',
    'droit_facture_particulier',
    'droit_devis',
    'droit_rapports',
]

def _appliquer_droits(employe, data):
    """Coche/décoche chaque droit selon les données POST."""
    for droit in DROITS:
        setattr(employe, droit, data.get(droit) in ('1', 'true', 'on', True))


def _employe_dict(u):
    """Sérialise un employé pour les réponses JSON."""
    return {
        'id':           u.pk,
        'nom':          u.nom,
        'postnom':      u.postnom,
        'prenom':       u.prenom,
        'nom_complet':  u.nom_complet,
        'initiales':    u.initiales,
        'username':     u.username,
        'email':        u.email or '',
        'type_poste':   u.type_poste,
        'type_poste_display': u.get_type_poste_display(),
        'actif':        u.actif,
        **{droit: getattr(u, droit) for droit in DROITS},
    }

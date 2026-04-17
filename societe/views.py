# societe/views.py — VERSION CORRIGÉE ET AMÉLIORÉE

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.exceptions import PermissionDenied


from .models import Societe
from .forms import SocieteInscriptionChefForm, SocieteUpdateForm  # ← Nous utilisons ce formulaire dédié au chef


@login_required
def societe_liste(request):
    """
    Page principale du profil de la société pour le chef.
    """
    societe = request.user.societe

    if not societe:
        return render(request, 'societe/liste.html', {
            'societe': None,
            'form': None,
            'error': "Vous n'êtes associé à aucune société."
        })

    # Formulaire pour modification (seulement les champs autorisés pour le chef)
    form = SocieteInscriptionChefForm(instance=societe)

    # Données pour affichage clair
    identity_rows = [
        ('Raison sociale',    societe.nom,                        'bi-building'),
        ('NIF',               societe.nif,                        'bi-fingerprint'),
        ('Gérant',            societe.nom_complet_gerant or '—',  'bi-person'),
        ('Email société',     societe.email_societe or '—',       'bi-envelope'),
        ('Téléphone',         societe.telephone or '—',           'bi-telephone'),
        ('Registre commerce', societe.registre or '—',            'bi-file-earmark-text'),
        ('Boîte postale',     societe.boite_postal or '—',        'bi-mailbox'),
        ('Secteur d\'activité', societe.secteur or '—',           'bi-briefcase'),
        ('Forme juridique',   societe.forme or '—',               'bi-building'),
    ]

    fiscal_rows = [
        ('Centre fiscal',     societe.get_centre_fiscale_display() or '—', 'bi-bank'),
        ('Assujetti TVA',     'Oui' if societe.assujeti_tva else 'Non', 'bi-receipt'),
        ('Assujetti TC',      'Oui' if societe.assujeti_tc else 'Non',  'bi-cash-stack'),
        ('Assujetti PFL',     'Oui' if societe.assujeti_pfl else 'Non', 'bi-percent'),
    ]

    address_rows = [
        ('Province',           societe.province or '—',           'bi-map'),
        ('Commune',            societe.commune or '—',            'bi-shop'),
        ('Quartier',           societe.quartier or '—',           'bi-geo'),
        ('Avenue',             societe.avenue or '—',             'bi-signpost'),
        ('Numéro',             societe.numero or '—',             'bi-hash'),
        ('Adresse complète',   societe.adresse_complete or '—',   'bi-house'),
    ]

    return render(request, 'societe/liste.html', {
        'societe':       societe,
        'form':          form,
        'identity_rows': identity_rows,
        'fiscal_rows':   fiscal_rows,      # ← Nouveau : fiscalité séparée
        'address_rows':  address_rows,
        'has_societe':   True,
    })


@login_required
@require_POST
def ajax_modifier(request):
    """
    Modification AJAX des informations de la société par le chef.
    """
    societe = request.user.societe

    if not societe:
        return JsonResponse({'ok': False, 'error': 'Aucune société associée à votre compte.'}, status=400)

    # Sécurité : seul le directeur ou superuser peut modifier
    if not (request.user.is_superuser or request.user.type_poste == 'DIRECTEUR'):
        return JsonResponse({'ok': False, 'error': 'Vous n\'avez pas les droits pour modifier ces informations.'}, status=403)

    #form = SocieteInscriptionChefForm(request.POST, request.FILES, instance=societe)
    form = SocieteUpdateForm(request.POST, request.FILES, instance=societe)

    if form.is_valid():
        societe = form.save()

        return JsonResponse({
            'ok': True,
            'message': 'Informations de la société mises à jour avec succès.',
            'data': {
                'nom': societe.nom,
                'nif': societe.nif,
                'nom_complet_gerant': societe.nom_complet_gerant or '—',
                'email_societe': societe.email_societe or '—',
                'secteur': societe.secteur or '—',
                'forme': societe.forme or '—',
                'telephone': societe.telephone or '—',
                'logo_url': societe.logo.url if societe.logo else None,
            }
        })

    # Erreurs de validation
    errors = {field: error_list[0] for field, error_list in form.errors.items()}

    return JsonResponse({
        'ok': False,
        'errors': errors,
        'message': 'Veuillez corriger les erreurs indiquées.'
    }, status=400)
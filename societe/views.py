from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.exceptions import PermissionDenied

from .models import Societe
from .forms import SocieteInscriptionChefForm, SocieteUpdateForm


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

    # === FORMULAIRE CORRIGÉ : On utilise SocieteUpdateForm pour avoir tous les champs ===
    form = SocieteUpdateForm(instance=societe)

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
        'form':          form,                    # ← Important : maintenant SocieteUpdateForm
        'identity_rows': identity_rows,
        'fiscal_rows':   fiscal_rows,
        'address_rows':  address_rows,
        'has_societe':   True,
    })


@login_required
@require_POST
def ajax_modifier(request):
    societe = getattr(request.user, 'societe', None)
    if not societe:
        return JsonResponse({'ok': False, 'error': 'Aucune société associée.'}, status=400)

    form = SocieteUpdateForm(request.POST, request.FILES, instance=societe)

    if form.is_valid():
        form.save()
        return JsonResponse({'ok': True, 'message': 'Mise à jour réussie !'})

    # === AFFICHAGE DÉTAILLÉ DES ERREURS ===
    print("=== ERREURS FORMULAIRE ===")
    print(form.errors)                    # Dans le terminal
    print(form.errors.as_json())          # Version JSON

    return JsonResponse({
        'ok': False,
        'message': 'Erreurs de validation',
        'errors': form.errors.get_json_data()   # Plus détaillé
    }, status=400)
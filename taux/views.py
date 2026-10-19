# taux/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import TauxTVA, TauxTC, TauxPFL
from .forms import TauxForm, FORMS_PAR_TYPE, TYPE_TAUX_CHOICES

MODELES_PAR_TYPE = {'TVA': TauxTVA, 'TC': TauxTC, 'PFL': TauxPFL}


def _normaliser_type(type_taux):
    t = (type_taux or 'TVA').upper()
    return t if t in MODELES_PAR_TYPE else 'TVA'


def _check_droit(request):
    societe = getattr(request.user, 'societe', None)
    if not societe:
        return None, "Vous n'êtes rattaché à aucune société."
    type_poste = getattr(request.user, 'type_poste', None)
    if type_poste != 'DIRECTEUR':
        return None, "Seul le directeur peut gérer les taux TVA."
    return societe, None


@login_required
def taux_liste(request):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    mode_production = societe.obr_mode_production
    liste_tva = TauxTVA.objects.filter(societe=societe, obr_mode_envoye=mode_production)
    liste_tc = TauxTC.objects.filter(societe=societe, obr_mode_envoye=mode_production)
    liste_pfl = TauxPFL.objects.filter(societe=societe, obr_mode_envoye=mode_production)
    combines = (
        [{'obj': t, 'type': 'TVA'} for t in liste_tva] +
        [{'obj': t, 'type': 'TC'} for t in liste_tc] +
        [{'obj': t, 'type': 'PFL'} for t in liste_pfl]
    )
    return render(request, 'taux/liste.html', {
        'taux':  combines,
        'total': len(combines),
    })


@login_required
def taux_creer(request, type_taux='TVA'):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    if request.method == 'POST':
        type_taux = _normaliser_type(request.POST.get('type_taux', type_taux))
    else:
        type_taux = _normaliser_type(request.GET.get('type', type_taux))
    form_class = FORMS_PAR_TYPE[type_taux]

    if request.method == 'POST':
        form = form_class(request.POST, societe=societe)
        if form.is_valid():
            t = form.save()
            messages.success(request, f"Taux {type_taux} « {t.nom} » créé avec succès.")
            return redirect('taux:liste')
    else:
        form = form_class(societe=societe)

    return render(request, 'taux/form.html', {
        'form':   form,
        'titre':  f'Nouveau taux {type_taux}',
        'action': 'Créer',
        'type_taux': type_taux,
        'types_taux': TYPE_TAUX_CHOICES,
        'creation': True,
    })


@login_required
def taux_modifier(request, pk, type_taux='TVA'):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    type_taux = _normaliser_type(type_taux)
    modele = MODELES_PAR_TYPE[type_taux]
    form_class = FORMS_PAR_TYPE[type_taux]
    mode_production = societe.obr_mode_production
    taux = get_object_or_404(modele, pk=pk, societe=societe, obr_mode_envoye=mode_production)

    if request.method == 'POST':
        form = form_class(request.POST, instance=taux, societe=societe)
        if form.is_valid():
            form.save()
            messages.success(request, f"Taux {type_taux} « {taux.nom} » modifié avec succès.")
            return redirect('taux:liste')
    else:
        form = form_class(instance=taux, societe=societe)

    return render(request, 'taux/form.html', {
        'form':   form,
        'titre':  f'Modifier le taux {type_taux}',
        'action': 'Enregistrer',
        'taux':   taux,
        'type_taux': type_taux,
        'types_taux': TYPE_TAUX_CHOICES,
        'creation': False,
    })


@login_required
def taux_supprimer(request, pk, type_taux='TVA'):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    type_taux = _normaliser_type(type_taux)
    modele = MODELES_PAR_TYPE[type_taux]
    mode_production = societe.obr_mode_production
    taux = get_object_or_404(modele, pk=pk, societe=societe, obr_mode_envoye=mode_production)

    if request.method == 'POST':
        # Protection : vérifier si des produits ou services utilisent ce taux
        nb_produits = getattr(taux, 'produits', None)
        nb_services = getattr(taux, 'services', None)
        
        if (nb_produits and nb_produits.exists()) or (nb_services and nb_services.exists()):
            messages.error(request, f"Impossible de supprimer « {taux.nom} » : des produits ou services lui sont associés.")
            return redirect('taux:liste')

        nom = taux.nom
        taux.delete()
        messages.success(request, f"Taux « {nom} » supprimé.")
        return redirect('taux:liste')

    return render(request, 'taux/supprimer.html', {'taux': taux, 'type_taux': type_taux})
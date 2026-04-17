# taux/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Taux
from .forms import TauxForm


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

    liste = Taux.objects.filter(societe=societe)
    return render(request, 'taux/liste.html', {
        'taux':  liste,
        'total': liste.count(),
    })


@login_required
def taux_creer(request):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    if request.method == 'POST':
        form = TauxForm(request.POST, societe=societe)
        if form.is_valid():
            t = form.save()
            messages.success(request, f"Taux « {t.nom} » créé avec succès.")
            return redirect('taux:liste')
    else:
        form = TauxForm(societe=societe)

    return render(request, 'taux/form.html', {
        'form':   form,
        'titre':  'Nouveau taux TVA',
        'action': 'Créer',
    })


@login_required
def taux_modifier(request, pk):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    taux = get_object_or_404(Taux, pk=pk, societe=societe)

    if request.method == 'POST':
        form = TauxForm(request.POST, instance=taux, societe=societe)
        if form.is_valid():
            form.save()
            messages.success(request, f"Taux « {taux.nom} » modifié avec succès.")
            return redirect('taux:liste')
    else:
        form = TauxForm(instance=taux, societe=societe)

    return render(request, 'taux/form.html', {
        'form':   form,
        'titre':  'Modifier le taux TVA',
        'action': 'Enregistrer',
        'taux':   taux,
    })


@login_required
def taux_supprimer(request, pk):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    taux = get_object_or_404(Taux, pk=pk, societe=societe)

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

    return render(request, 'taux/supprimer.html', {'taux': taux})

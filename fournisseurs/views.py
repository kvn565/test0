# fournisseurs/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from .models import Fournisseur
from .forms import FournisseurForm


def _check_droit(request):
    societe = getattr(request.user, 'societe', None)
    if not societe:
        return None, "Vous n'êtes rattaché à aucune société."
    type_poste = getattr(request.user, 'type_poste', None)
    if type_poste != 'DIRECTEUR' and not getattr(request.user, 'droit_stock_fournisseur', False):
        return None, "Vous n'avez pas les droits pour gérer les fournisseurs."
    return societe, None


@login_required
def fournisseur_liste(request):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    q = request.GET.get('q', '')
    fournisseurs = Fournisseur.objects.filter(societe=societe)
    if q:
        fournisseurs = fournisseurs.filter(
            Q(nom__icontains=q) | Q(telephone__icontains=q) | Q(adresse__icontains=q)
        )
    return render(request, 'fournisseurs/liste.html', {
        'fournisseurs': fournisseurs,
        'q':            q,
        'total':        Fournisseur.objects.filter(societe=societe).count(),
    })


@login_required
def fournisseur_creer(request):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    if request.method == 'POST':
        form = FournisseurForm(request.POST, societe=societe)
        if form.is_valid():
            f = form.save()
            messages.success(request, f"Fournisseur « {f.nom} » créé avec succès.")
            return redirect('fournisseurs:liste')
    else:
        form = FournisseurForm(societe=societe)

    return render(request, 'fournisseurs/form.html', {
        'form':   form,
        'titre':  'Nouveau fournisseur',
        'action': 'Créer',
    })


@login_required
def fournisseur_modifier(request, pk):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    fournisseur = get_object_or_404(Fournisseur, pk=pk, societe=societe)

    if request.method == 'POST':
        form = FournisseurForm(request.POST, instance=fournisseur, societe=societe)
        if form.is_valid():
            form.save()
            messages.success(request, f"Fournisseur « {fournisseur.nom} » modifié avec succès.")
            return redirect('fournisseurs:liste')
    else:
        form = FournisseurForm(instance=fournisseur, societe=societe)

    return render(request, 'fournisseurs/form.html', {
        'form':        form,
        'titre':       'Modifier le fournisseur',
        'action':      'Enregistrer',
        'fournisseur': fournisseur,
    })


@login_required
def fournisseur_supprimer(request, pk):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    fournisseur = get_object_or_404(Fournisseur, pk=pk, societe=societe)

    if request.method == 'POST':
        # Protection : vérifier s'il y a des produits liés
        nb_produits = getattr(fournisseur, 'produits', None)
        if nb_produits and nb_produits.exists():
            messages.error(request, f"Impossible de supprimer « {fournisseur.nom} » : des produits lui sont associés.")
            return redirect('fournisseurs:liste')

        nom = fournisseur.nom
        fournisseur.delete()
        messages.success(request, f"Fournisseur « {nom} » supprimé.")
        return redirect('fournisseurs:liste')

    return render(request, 'fournisseurs/supprimer.html', {'fournisseur': fournisseur})

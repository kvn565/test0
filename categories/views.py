# categories/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from .models import Categorie
from .forms import CategorieForm


def _get_societe(request):
    """Retourne la société de l'utilisateur connecté."""
    return getattr(request.user, 'societe', None)


def _check_droit(request):
    """
    Vérifie que l'utilisateur a le droit stock catégorie.
    Retourne (societe, erreur) — erreur est None si OK.
    """
    if request.user.is_superuser:
        return None, "Superadmin n'a pas de société directe."

    societe = _get_societe(request)
    if not societe:
        return None, "Aucune société associée à votre compte."

    if not (request.user.droit_stock_categorie or request.user.type_poste == 'DIRECTEUR'):
        return None, "Vous n'avez pas les droits pour gérer les catégories."

    return societe, None


# ─────────────────────────────────────────────────────────────────
#  LISTE
# ─────────────────────────────────────────────────────────────────

@login_required
def liste_categories(request):
    societe, err = _check_droit(request)
    if err:
        messages.error(request, err)
        return redirect('accueil')

    # ✅ Filtre par société — chef voit UNIQUEMENT ses catégories
    categories = Categorie.objects.filter(societe=societe)

    # Recherche rapide
    q = request.GET.get('q', '').strip()
    if q:
        categories = categories.filter(nom__icontains=q)

    return render(request, 'categories/liste.html', {
        'categories': categories,
        'q':          q,
        'total':      Categorie.objects.filter(societe=societe).count(),
    })


# ─────────────────────────────────────────────────────────────────
#  CRÉER
# ─────────────────────────────────────────────────────────────────

@login_required
def categorie_creer(request):
    societe, err = _check_droit(request)
    if err:
        messages.error(request, err)
        return redirect('accueil')

    if request.method == 'POST':
        form = CategorieForm(societe=societe, data=request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ Catégorie « {form.cleaned_data['nom']} » créée avec succès.")
            return redirect('categories:liste')
    else:
        form = CategorieForm(societe=societe)

    return render(request, 'categories/form.html', {
        'form':  form,
        'titre': 'Nouvelle catégorie',
        'mode':  'creer',
    })


# ─────────────────────────────────────────────────────────────────
#  MODIFIER
# ─────────────────────────────────────────────────────────────────

@login_required
def categorie_modifier(request, pk):
    societe, err = _check_droit(request)
    if err:
        messages.error(request, err)
        return redirect('accueil')

    # ✅ get_object_or_404 filtre aussi par société — empêche un chef
    # de modifier les catégories d'une autre société via l'URL
    categorie = get_object_or_404(Categorie, pk=pk, societe=societe)

    if request.method == 'POST':
        form = CategorieForm(societe=societe, data=request.POST, instance=categorie)
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ Catégorie « {categorie.nom} » mise à jour.")
            return redirect('categories:liste')
    else:
        form = CategorieForm(societe=societe, instance=categorie)

    return render(request, 'categories/form.html', {
        'form':      form,
        'titre':     f'Modifier — {categorie.nom}',
        'categorie': categorie,
        'mode':      'modifier',
    })


# ─────────────────────────────────────────────────────────────────
#  SUPPRIMER
# ─────────────────────────────────────────────────────────────────

@login_required
def categorie_supprimer(request, pk):
    societe, err = _check_droit(request)
    if err:
        messages.error(request, err)
        return redirect('accueil')

    # ✅ Filtre par société — sécurité
    categorie = get_object_or_404(Categorie, pk=pk, societe=societe)

    if request.method == 'POST':
        nom = categorie.nom
        nb  = categorie.nb_produits

        if nb > 0:
            # Protéger les catégories qui ont des produits
            messages.error(
                request,
                f"❌ Impossible de supprimer « {nom} » : {nb} produit(s) lui sont associés. "
                f"Réaffectez-les d'abord à une autre catégorie."
            )
            return redirect('categories:liste')

        categorie.delete()
        messages.success(request, f"✅ Catégorie « {nom} » supprimée.")
        return redirect('categories:liste')

    return render(request, 'categories/supprimer.html', {
        'categorie': categorie,
    })

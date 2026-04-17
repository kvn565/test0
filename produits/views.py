from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.db import transaction
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from .models import Produit
from .forms import ProduitForm
from .obr_service import OBRService
from categories.models import Categorie


def _check_droit(request):
    """Vérifie les droits d'accès aux produits"""
    societe = getattr(request.user, 'societe', None)
    if not societe:
        return None, "Vous n'êtes rattaché à aucune société."

    type_poste = getattr(request.user, 'type_poste', None)
    has_right = (
        type_poste == 'DIRECTEUR' or
        getattr(request.user, 'droit_stock_produit', False)
    )
    if not has_right:
        return None, "Vous n'avez pas les droits pour gérer les produits."

    return societe, None


# ── LISTE DES PRODUITS ───────────────────────────────────────────────────────
@login_required
def produit_liste(request):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    q             = request.GET.get('q', '').strip()
    origine       = request.GET.get('origine', '')
    statut_filtre = request.GET.get('statut', '')
    categorie_id  = request.GET.get('categorie', '')
    page_num      = request.GET.get('page', 1)          # ← Ajout pour la pagination

    produits = Produit.objects.filter(societe=societe)\
        .select_related('categorie', 'taux_tva')\
        .order_by('-date_creation', 'designation')   # Ordre recommandé

    if q:
        produits = produits.filter(
            Q(code__icontains=q) |
            Q(designation__icontains=q) |
            Q(unite__icontains=q)
        )
    if origine:
        produits = produits.filter(origine=origine)
    if statut_filtre:
        produits = produits.filter(statut=statut_filtre)
    if categorie_id:
        produits = produits.filter(categorie_id=categorie_id)

    # ====================== PAGINATION ======================
    paginator = Paginator(produits, 5)   # 5 produits par page

    try:
        produits_page = paginator.page(page_num)
    except PageNotAnInteger:
        produits_page = paginator.page(1)
    except EmptyPage:
        produits_page = paginator.page(paginator.num_pages)

    # Statistiques (sur tous les produits, pas seulement la page courante)
    base_qs = Produit.objects.filter(societe=societe)
    stats = {
        'total': base_qs.count(),
        'actifs': base_qs.filter(statut='ACTIF').count(),
        'locaux': base_qs.filter(origine='LOCAL').count(),
        'importes': base_qs.filter(origine='IMPORTE').count(),
        'importes_incomplets': base_qs.filter(
            origine='IMPORTE',
            reference_dmc='',
            rubrique_tarifaire='',
            nombre_par_paquet__isnull=True
        ).count(),
    }

    return render(request, 'produits/produit_liste.html', {
        'produits':     produits_page,      # ← Objet paginé (important !)
        'categories':   Categorie.objects.filter(societe=societe).order_by('nom'),
        'stats':        stats,
        'q':            q,
        'origine':      origine,
        'statut':       statut_filtre,
        'categorie_id': categorie_id,
        'paginator':    paginator,          # Pour le template
        'page_obj':     produits_page,      # Recommandé par Django
    })


# ── CRÉER PRODUIT LOCAL ──────────────────────────────────────────────────────
@login_required
def produit_creer_local(request):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    if request.method == 'POST':
        form = ProduitForm(request.POST, societe=societe, origine='LOCAL')
        if form.is_valid():
            produit = form.save()                    # Plus besoin de commit=False + origine=
            messages.success(request, f"Produit local « {produit.designation} » créé.")
            return redirect('produits:liste')
    else:
        form = ProduitForm(societe=societe, origine='LOCAL')

    return render(request, 'produits/produit_form.html', {
        'form':        form,
        'titre':       'Nouveau Produit Local',
        'action':      'Créer',
        'origine':     'LOCAL',
        'est_importe': False,
    })


@login_required
def produit_creer_importe(request):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    if request.method == 'POST':
        form = ProduitForm(request.POST, societe=societe, origine='IMPORTE')
        if form.is_valid():
            produit = form.save()
            messages.success(request, f"Produit importé « {produit.designation} » créé avec succès.")
            return redirect('produits:liste')
        else:
            # === AFFICHE LES ERREURS POUR DEBUG ===
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
            print("Erreurs formulaire :", form.errors)   # à voir dans la console
    else:
        form = ProduitForm(societe=societe, origine='IMPORTE')

    return render(request, 'produits/produit_form.html', {
        'form': form,
        'titre': 'Nouveau Produit Importé',
        'action': 'Créer',
        'origine': 'IMPORTE',
        'est_importe': True,
    })
# ── MODIFIER PRODUIT ─────────────────────────────────────────────────────────
# ── MODIFIER PRODUIT ─────────────────────────────────────────────────────────
@login_required
def produit_modifier(request, pk):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    produit = get_object_or_404(
        Produit.objects.select_related('categorie', 'taux_tva'),
        pk=pk, societe=societe
    )

    if request.method == 'POST':
        form = ProduitForm(
            request.POST, 
            instance=produit, 
            societe=societe, 
            origine=produit.origine   # ← Correction importante
        )
        if form.is_valid():
            with transaction.atomic():
                produit = form.save()   # On récupère l'instance sauvegardée
            messages.success(request, f"Produit « {produit.designation} » modifié.")
            return redirect('produits:liste')
    else:
        form = ProduitForm(
            instance=produit, 
            societe=societe, 
            origine=produit.origine   # ← Correction importante
        )

    return render(request, 'produits/produit_form.html', {
        'form':        form,
        'titre':       f"Modifier {produit.designation}",
        'action':      'Enregistrer',
        'produit':     produit,
        'origine':     produit.origine,
        'est_importe': produit.origine == 'IMPORTE',
    })

# ── SUPPRIMER PRODUIT ────────────────────────────────────────────────────────
@login_required
@require_POST
def produit_supprimer(request, pk):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    produit = get_object_or_404(Produit, pk=pk, societe=societe)

    if produit.entrees_stock.exists():
        messages.error(request, f"Impossible de supprimer « {produit.designation} » : entrées stock associées.")
        return redirect('produits:liste')

    nom = produit.designation
    produit.delete()
    messages.success(request, f"Produit « {nom} » supprimé.")
    return redirect('produits:liste')


# ── AJAX : Importer infos depuis DMC (OBR) ───────────────────────────────────
@login_required
@require_POST
def ajax_importer_dmc(request):
    """Importe les informations DMC depuis OBR"""
    societe, erreur = _check_droit(request)
    if erreur:
        return JsonResponse({'success': False, 'error': erreur}, status=403)

    reference_dmc = request.POST.get('reference_dmc', '').strip()
    if not reference_dmc:
        return JsonResponse({
            'success': False,
            'error': "Référence DMC requise."
        }, status=400)

    try:
        # Appel au service OBR (version corrigée que je t'ai donnée précédemment)
        data = OBRService.get_dmc_info(societe, reference_dmc)

        return JsonResponse({
            'success': True,           # Changé de 'ok' à 'success' pour correspondre au JS
            'data': data,
            'message': "Données importées avec succès depuis OBR."
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e) or "Erreur lors de la récupération des données OBR."
        }, status=400)
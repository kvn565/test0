# produits/views.py
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.db import transaction
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from .models import Produit
from .forms import ProduitForm
from .obr_service import OBRService
from categories.models import Categorie


# ─── HELPER UNIQUE ────────────────────────────────────────────────────────────

def _check_droit(request):
    """
    Vérifie les droits d'accès aux produits.
    Retourne (societe, erreur) — l'un des deux est None.

    ✅ Helper unique : suppression du doublon _get_societe_and_check_droit.
    """
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


# ─── LISTE DES PRODUITS ───────────────────────────────────────────────────────

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
    page_num      = request.GET.get('page', 1)

    produits = (
        Produit.objects
        .filter(societe=societe)
        .select_related('categorie', 'taux_tva')
        .order_by('-date_creation', 'designation')
    )

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

    # ── Pagination ────────────────────────────────────────────────────────────
    paginator = Paginator(produits, 5)
    try:
        produits_page = paginator.page(page_num)
    except PageNotAnInteger:
        produits_page = paginator.page(1)
    except EmptyPage:
        produits_page = paginator.page(paginator.num_pages)

    # ── Statistiques (sur tous les produits, pas seulement la page) ──────────
    base_qs = Produit.objects.filter(societe=societe)

    # ✅ FIX 3 : OR au lieu de AND pour capturer tout produit importé
    #            avec AU MOINS un champ OBR manquant
    incomplets_qs = base_qs.filter(origine='IMPORTE').filter(
        Q(reference_dmc='') |
        Q(rubrique_tarifaire='') |
        Q(nombre_par_paquet__isnull=True) |
        Q(description_paquet='')
    )

    stats = {
        'total':                base_qs.count(),
        'actifs':               base_qs.filter(statut='ACTIF').count(),
        'locaux':               base_qs.filter(origine='LOCAL').count(),
        'importes':             base_qs.filter(origine='IMPORTE').count(),
        'importes_incomplets':  incomplets_qs.count(),
    }

    return render(request, 'produits/produit_liste.html', {
        'produits':     produits_page,
        'categories':   Categorie.objects.filter(societe=societe).order_by('nom'),
        'stats':        stats,
        'q':            q,
        'origine':      origine,
        'statut':       statut_filtre,
        'categorie_id': categorie_id,
        'paginator':    paginator,
        'page_obj':     produits_page,
    })


# ─── CRÉER PRODUIT LOCAL ──────────────────────────────────────────────────────

@login_required
def produit_creer_local(request):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    if request.method == 'POST':
        form = ProduitForm(request.POST, societe=societe, origine='LOCAL')
        if form.is_valid():
            produit = form.save()
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


# ─── CRÉER PRODUIT IMPORTÉ ────────────────────────────────────────────────────

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
            messages.success(
                request,
                f"Produit importé « {produit.designation} » créé avec succès."
            )
            return redirect('produits:liste')
        # ✅ FIX 2 : Suppression des messages.error et print() de debug.
        #            Les erreurs s'affichent via form.errors dans le template.
    else:
        form = ProduitForm(societe=societe, origine='IMPORTE')

    return render(request, 'produits/produit_form.html', {
        'form':        form,
        'titre':       'Nouveau Produit Importé',
        'action':      'Créer',
        'origine':     'IMPORTE',
        'est_importe': True,
    })


# ─── MODIFIER PRODUIT ─────────────────────────────────────────────────────────

@login_required
def produit_modifier(request, pk):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    produit = get_object_or_404(
        Produit.objects.select_related('categorie', 'taux_tva'),
        pk=pk,
        societe=societe
    )

    if request.method == 'POST':
        form = ProduitForm(
            request.POST,
            instance=produit,
            societe=societe,
            origine=produit.origine,
        )
        if form.is_valid():
            with transaction.atomic():
                produit = form.save()
            messages.success(request, f"Produit « {produit.designation} » modifié.")
            return redirect('produits:liste')
    else:
        form = ProduitForm(
            instance=produit,
            societe=societe,
            origine=produit.origine,
        )

    return render(request, 'produits/produit_form.html', {
        'form':        form,
        'titre':       f"Modifier {produit.designation}",
        'action':      'Enregistrer',
        'produit':     produit,
        'origine':     produit.origine,
        'est_importe': produit.origine == 'IMPORTE',
    })


# ─── SUPPRIMER PRODUIT ────────────────────────────────────────────────────────

@login_required
@require_POST
def produit_supprimer(request, pk):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    produit = get_object_or_404(Produit, pk=pk, societe=societe)

    # ✅ FIX 4 : Vérifier entrées stock ET lignes de facture avant suppression.
    #            Adapter 'lignes' selon le related_name réel dans ton modèle LigneFacture.
    a_des_entrees = produit.entrees_stock.exists()
    a_des_lignes  = hasattr(produit, 'lignes') and produit.lignes.exists()

    if a_des_entrees or a_des_lignes:
        messages.error(
            request,
            f"Impossible de supprimer « {produit.designation} » : "
            f"il est lié à des entrées de stock ou des lignes de facture."
        )
        return redirect('produits:liste')

    nom = produit.designation
    produit.delete()
    messages.success(request, f"Produit « {nom} » supprimé.")
    return redirect('produits:liste')


# ─── AJAX : Importer infos depuis DMC (OBR) ──────────────────────────────────

@login_required
@require_POST
def ajax_importer_dmc(request):
    import traceback  # ← temporaire

    societe, erreur = _check_droit(request)
    if erreur:
        return JsonResponse({'success': False, 'error': erreur}, status=403)

    reference_dmc = request.POST.get('reference_dmc', '').strip()
    if not reference_dmc:
        return JsonResponse(
            {'success': False, 'error': "Référence DMC requise."},
            status=400
        )

    try:
        data = OBRService.get_dmc_info(societe, reference_dmc)
        return JsonResponse({'success': True, 'data': data})
    except Exception as e:
        # ← Log complet dans la console Django
        traceback.print_exc()
        return JsonResponse(
            {'success': False, 'error': str(e)},
            status=400
        )

# ─── DÉTAIL D'UN PRODUIT ──────────────────────────────────────────────────────

@login_required
def produit_detail(request, pk):
    """Affichage détaillé d'un produit."""
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    produit = get_object_or_404(
        Produit.objects.select_related('categorie', 'taux_tva', 'societe'),
        pk=pk,
        societe=societe
    )

    return render(request, 'produits/produit_detail.html', {
        'produit':            produit,
        'est_importe':        produit.est_importe,
        'infos_obr_completes': produit.infos_obr_completes,
        'stock_disponible':   produit.stock_disponible,
        'prix_tvac':          produit.prix_vente_tvac,
        'tva_montant':        produit.tva_montant,
    })

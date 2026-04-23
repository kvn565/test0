# stock/views.py (complet et corrigé)
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q, Sum
from .models import EntreeStock, SortieStock
from .forms import EntreeStockForm, SortieStockForm
from .obr_service import envoyer_entree_stock, envoyer_sortie_stock
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


def _check_droit(request):
    societe = getattr(request.user, 'societe', None)
    if not societe:
        return None, "Vous n'êtes rattaché à aucune société."
    type_poste = getattr(request.user, 'type_poste', None)
    if type_poste != 'DIRECTEUR' and not getattr(request.user, 'droit_stock_produit', False):
        return None, "Vous n'avez pas les droits pour gérer le stock."
    return societe, None


# ═══════════════════════════════════════════════
#  ENTRÉES STOCK
# ═══════════════════════════════════════════════

@login_required
def entree_liste(request):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    q        = request.GET.get('q', '')
    statut   = request.GET.get('statut', '')
    type_mvt = request.GET.get('type', '')
    page_num = request.GET.get('page', 1)   # ← Ajout pour la pagination

    entrees = EntreeStock.objects.filter(societe=societe)\
        .select_related('produit', 'fournisseur')\
        .order_by('-date_creation')   # Important : ordonner les résultats

    if q:
        entrees = entrees.filter(
            Q(produit__designation__icontains=q) |
            Q(produit__code__icontains=q) |
            Q(numero_ref__icontains=q) |
            Q(fournisseur__nom__icontains=q)
        )
    if statut:
        entrees = entrees.filter(statut_obr=statut)
    if type_mvt:
        entrees = entrees.filter(type_entree=type_mvt)

    # ====================== PAGINATION ======================
    paginator = Paginator(entrees, 5)        # 5 éléments par page (comme tu as demandé)
    try:
        entrees_page = paginator.page(page_num)
    except PageNotAnInteger:
        entrees_page = paginator.page(1)
    except EmptyPage:
        entrees_page = paginator.page(paginator.num_pages)

    stats = {
        'total':      entrees.count(),
        'en_attente': entrees.filter(statut_obr='EN_ATTENTE').count(),
        'envoyes':    entrees.filter(statut_obr='ENVOYE').count(),
        'echecs':     entrees.filter(statut_obr='ECHEC').count(),
    }

    return render(request, 'stock/entree_liste.html', {
        'entrees':  entrees_page,           # ← On passe l'objet paginé
        'stats':    stats,
        'q':        q,
        'statut':   statut,
        'type_mvt': type_mvt,
        'types':    EntreeStock.TYPE_ENTREE_CHOICES,
        'statuts':  EntreeStock.STATUT_OBR_CHOICES,
        'paginator': paginator,             # Pour les infos dans le template
        'page_obj':  entrees_page,          # Recommandé par Django
    })


@login_required
def entree_creer(request):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    if request.method == 'POST':
        form = EntreeStockForm(request.POST, societe=societe)
        if form.is_valid():
            entree  = form.save()
            produit = entree.produit
            produit.prix_vente = entree.prix_vente_actuel
            produit.save()
            messages.success(request, f"Entrée stock enregistrée pour « {produit.designation} ».")

            # ── Envoi OBR en temps réel (le token est géré dans la fonction) ──
            success, msg_obr = envoyer_entree_stock(entree)

            if success:
                messages.success(request, f"✅ OBR : {msg_obr}")
            else:
                messages.warning(
                    request,
                    f"⚠️ Entrée enregistrée, mais l'envoi OBR a échoué : {msg_obr}. "
                    "Elle sera marquée en attente pour réenvoi."
                )

            return redirect('stock:entrees')
    else:
        form = EntreeStockForm(societe=societe)

    return render(request, 'stock/entree_form.html', {
        'form':   form,
        'titre':  'Nouvelle entrée stock',
        'action': 'Enregistrer',
    })


@login_required
def entree_modifier(request, pk):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    entree = get_object_or_404(EntreeStock, pk=pk, societe=societe)

    if request.method == 'POST':
        form = EntreeStockForm(request.POST, instance=entree, societe=societe)
        if form.is_valid():
            form.save()
            messages.success(request, "Entrée stock modifiée.")
            return redirect('stock:entrees')
    else:
        form = EntreeStockForm(instance=entree, societe=societe)

    return render(request, 'stock/entree_form.html', {
        'form':   form,
        'titre':  "Modifier l'entrée",
        'action': 'Enregistrer',
        'entree': entree,
    })


@login_required
def entree_detail(request, pk):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    entree = get_object_or_404(
        EntreeStock.objects.select_related('produit', 'fournisseur'),
        pk=pk, societe=societe
    )
    return render(request, 'stock/entree_detail.html', {'entree': entree})


@login_required
def entree_supprimer(request, pk):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    entree = get_object_or_404(EntreeStock, pk=pk, societe=societe)

    if request.method == 'POST':
        if entree.sorties.exists():
            messages.error(request, "Impossible de supprimer : des sorties stock sont liées à cette entrée.")
            return redirect('stock:entrees')
        entree.delete()
        messages.success(request, "Entrée stock supprimée.")
        return redirect('stock:entrees')

    return render(request, 'stock/entree_supprimer.html', {'entree': entree})


@login_required
def entree_reenvoyer_obr(request, pk):
    """Réenvoi manuel d'une entrée échouée à l'OBR."""
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    entree = get_object_or_404(EntreeStock, pk=pk, societe=societe)

    if entree.statut_obr == 'ENVOYE':
        messages.info(request, "Cette entrée a déjà été envoyée à l'OBR.")
        return redirect('stock:entree_detail', pk=pk)

    success, msg = envoyer_entree_stock(entree)

    if success:
        messages.success(request, f"✅ Réenvoi OBR réussi : {msg}")
    else:
        messages.error(request, f"❌ Réenvoi OBR échoué : {msg}")

    return redirect('stock:entree_detail', pk=pk)


# ═══════════════════════════════════════════════
#  SORTIES STOCK
# ═══════════════════════════════════════════════

@login_required
def sortie_liste(request):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    q        = request.GET.get('q', '')
    statut   = request.GET.get('statut', '')
    type_mvt = request.GET.get('type', '')
    page_num = request.GET.get('page', 1)

    sorties = SortieStock.objects.filter(societe=societe)\
        .select_related('entree_stock__produit')\
        .order_by('-date_creation')

    if q:
        sorties = sorties.filter(
            Q(entree_stock__produit__designation__icontains=q) |
            Q(entree_stock__produit__code__icontains=q) |
            Q(code__icontains=q)
        )
    if statut:
        sorties = sorties.filter(statut_obr=statut)
    if type_mvt:
        sorties = sorties.filter(type_sortie=type_mvt)

    # ====================== PAGINATION ======================
    paginator = Paginator(sorties, 5)
    try:
        sorties_page = paginator.page(page_num)
    except PageNotAnInteger:
        sorties_page = paginator.page(1)
    except EmptyPage:
        sorties_page = paginator.page(paginator.num_pages)

    stats = {
        'total':      sorties.count(),
        'en_attente': sorties.filter(statut_obr='EN_ATTENTE').count(),
        'envoyes':    sorties.filter(statut_obr='ENVOYE').count(),
        'echecs':     sorties.filter(statut_obr='ECHEC').count(),
    }

    return render(request, 'stock/sortie_liste.html', {
        'sorties':   sorties_page,
        'stats':     stats,
        'q':         q,
        'statut':    statut,
        'type_mvt':  type_mvt,
        'types':     SortieStock.TYPE_SORTIE_CHOICES,
        'statuts':   SortieStock.STATUT_OBR_CHOICES,
        'paginator': paginator,
        'page_obj':  sorties_page,
    })

@login_required
def sortie_creer(request):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    if request.method == 'POST':
        form = SortieStockForm(request.POST, societe=societe)
        if form.is_valid():
            sortie = form.save()
            messages.success(request, f"Sortie stock enregistrée pour « {sortie.produit.designation} ».")

            # Envoi OBR (le token est géré dans la fonction)
            success, msg_obr = envoyer_sortie_stock(sortie)
            if success:
                messages.success(request, f"✅ OBR : {msg_obr}")
            else:
                messages.warning(
                    request,
                    f"⚠️ Sortie enregistrée, mais l'envoi OBR a échoué : {msg_obr}. "
                    "Elle sera marquée en attente pour réenvoi."
                )

            return redirect('stock:sorties')
    else:
        form = SortieStockForm(societe=societe)

    return render(request, 'stock/sortie_form.html', {
        'form':   form,
        'titre':  'Nouvelle sortie stock',
        'action': 'Enregistrer',
    })


@login_required
def sortie_modifier(request, pk):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    sortie = get_object_or_404(SortieStock, pk=pk, societe=societe)

    if request.method == 'POST':
        form = SortieStockForm(request.POST, instance=sortie, societe=societe)
        if form.is_valid():
            form.save()
            messages.success(request, "Sortie stock modifiée.")
            return redirect('stock:sorties')
    else:
        form = SortieStockForm(instance=sortie, societe=societe)

    return render(request, 'stock/sortie_form.html', {
        'form':   form,
        'titre':  "Modifier la sortie",
        'action': 'Enregistrer',
        'sortie': sortie,
    })


@login_required
def sortie_detail(request, pk):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    sortie = get_object_or_404(
        SortieStock.objects.select_related('entree_stock__produit'),
        pk=pk, societe=societe
    )
    return render(request, 'stock/sortie_detail.html', {'sortie': sortie})


@login_required
def sortie_supprimer(request, pk):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    sortie = get_object_or_404(SortieStock, pk=pk, societe=societe)

    if request.method == 'POST':
        sortie.delete()
        messages.success(request, "Sortie stock supprimée.")
        return redirect('stock:sorties')

    return render(request, 'stock/sortie_supprimer.html', {'sortie': sortie})


@login_required
def sortie_reenvoyer_obr(request, pk):
    """Réenvoi manuel d'une sortie échouée à l'OBR."""
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    sortie = get_object_or_404(SortieStock, pk=pk, societe=societe)

    if sortie.statut_obr == 'ENVOYE':
        messages.info(request, "Cette sortie a déjà été envoyée à l'OBR.")
        return redirect('stock:sortie_detail', pk=pk)

    success, msg = envoyer_sortie_stock(sortie)

    if success:
        messages.success(request, f"✅ Réenvoi OBR réussi : {msg}")
    else:
        messages.error(request, f"❌ Réenvoi OBR échoué : {msg}")

    return redirect('stock:sortie_detail', pk=pk)


# ── AJAX : stock disponible d'une entrée ──────────────
@login_required
def stock_disponible(request):
    societe = getattr(request.user, 'societe', None)
    if not societe:
        return JsonResponse({'ok': False, 'error': 'Pas de société'})

    entree_id = request.GET.get('entree_id')
    try:
        entree = EntreeStock.objects.get(pk=entree_id, societe=societe)
        total_sorti = SortieStock.objects.filter(
            entree_stock=entree
        ).aggregate(total=Sum('quantite'))['total'] or 0
        dispo = float(entree.quantite) - float(total_sorti)
        return JsonResponse({
            'ok':           True,
            'produit':      entree.produit.designation,
            'code':         entree.produit.code,
            'unite':        entree.produit.unite,
            'origine':      entree.produit.origine,
            'prix':         float(entree.prix_vente_actuel),
            'dispo':        dispo,
            'total_entre':  float(entree.quantite),
        })
    except EntreeStock.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Entrée introuvable'})


@login_required
def refresh_obr(request, pk):
    """Réenvoie l'entrée échouée à l'OBR pour AJAX."""
    societe, erreur = _check_droit(request)
    if erreur:
        return JsonResponse({'ok': False, 'message': erreur})

    entree = get_object_or_404(EntreeStock, pk=pk, societe=societe)

    if entree.statut_obr == 'ENVOYE':
        return JsonResponse({'ok': True, 'message': "Cette entrée a déjà été envoyée à l'OBR."})

    success, msg_obr = envoyer_entree_stock(entree)

    if success:
        entree.statut_obr = 'ENVOYE'
        entree.save()
        return JsonResponse({'ok': True, 'message': f"✅ Réenvoi OBR réussi : {msg_obr}", 'statut': 'ENVOYE'})
    else:
        entree.statut_obr = 'ECHEC'
        entree.save()
        return JsonResponse({'ok': False, 'message': f"❌ Réenvoi OBR échoué : {msg_obr}", 'statut': 'ECHEC'})
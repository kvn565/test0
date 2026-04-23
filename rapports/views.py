from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
from decimal import Decimal
from django.utils import timezone

from produits.models import Produit
from services.models import Service
from stock.models import EntreeStock, SortieStock
from facturer.models import Facture, LigneFacture

from .utils import generer_excel, generer_pdf


# ══════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════
def _check_droit(request):
    societe = getattr(request.user, 'societe', None)
    if not societe:
        return None, "Vous n'êtes rattaché à aucune société."
    type_poste = getattr(request.user, 'type_poste', None)
    if type_poste != 'DIRECTEUR' and not getattr(request.user, 'droit_rapports', False):
        return None, "Vous n'avez pas les droits pour accéder aux rapports."
    return societe, None


def get_filtres(request):
    return {
        'date_debut': request.GET.get('date_debut', ''),
        'date_fin':   request.GET.get('date_fin', ''),
        'produit_id': request.GET.get('produit', ''),
        'service_id': request.GET.get('service', ''),
    }


def ctx_commun(f, societe):
    return {
        **f,
        'produits': Produit.objects.filter(societe=societe, statut='ACTIF').order_by('designation'),
        'services': Service.objects.filter(societe=societe, statut='ACTIF').order_by('designation'),
    }


# ══════════════════════════════════════════════
#  RAPPORTS PRINCIPAUX
# ══════════════════════════════════════════════
@login_required
def rapport_entrees(request):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    f = get_filtres(request)

    qs = EntreeStock.objects.filter(societe=societe).select_related(
        'produit', 'produit__categorie', 'fournisseur'
    ).order_by('-date_entree')

    if f['date_debut']:
        qs = qs.filter(date_entree__gte=f['date_debut'])
    if f['date_fin']:
        qs = qs.filter(date_entree__lte=f['date_fin'])
    if f['produit_id']:
        qs = qs.filter(produit__id=f['produit_id'])

    totaux = qs.aggregate(nb=Count('id'), total_qte=Sum('quantite'))
    totaux['total_valeur'] = sum(e.montant_total for e in qs)

    return render(request, 'rapports/entrees.html', {
        **ctx_commun(f, societe),
        'lignes': qs,
        'totaux': totaux,
        'titre': 'Entrées / Achats',
        'rapport': 'entrees',
        'rapport_icone': 'bi-box-arrow-in-down',
        'rapport_clr': '#0284c7',
    })


@login_required
def rapport_cout_stock(request):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    f = get_filtres(request)

    qs = LigneFacture.objects.filter(facture__societe=societe).select_related(
        'facture', 'facture__client', 'produit', 'service'
    ).order_by('-facture__date_facture')

    if f['date_debut']:
        qs = qs.filter(facture__date_facture__gte=f['date_debut'])
    if f['date_fin']:
        qs = qs.filter(facture__date_facture__lte=f['date_fin'])
    if f['produit_id']:
        qs = qs.filter(produit__id=f['produit_id'])
    if f['service_id']:
        qs = qs.filter(service__id=f['service_id'])

    ll = list(qs)

    return render(request, 'rapports/cout_stock.html', {
        **ctx_commun(f, societe),
        'lignes': ll,
        'nb': len(ll),
        'total_ht': sum(l.montant_ht for l in ll),
        'total_tva': sum(l.montant_tva for l in ll),
        'total_ttc': sum(l.montant_ttc for l in ll),
        'titre': 'Coût du Stock Vendu',
        'rapport': 'cout_stock',
        'rapport_icone': 'bi-calculator',
        'rapport_clr': '#b45309',
    })


@login_required
def rapport_sorties(request):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    f = get_filtres(request)

    qs = SortieStock.objects.filter(societe=societe).select_related(
        'entree_stock', 'entree_stock__produit', 'entree_stock__produit__categorie'
    ).order_by('-date_sortie')

    if f['date_debut']:
        qs = qs.filter(date_sortie__gte=f['date_debut'])
    if f['date_fin']:
        qs = qs.filter(date_sortie__lte=f['date_fin'])
    if f['produit_id']:
        qs = qs.filter(entree_stock__produit__id=f['produit_id'])

    totaux = qs.aggregate(nb=Count('id'), total_qte=Sum('quantite'))
    totaux['total_valeur'] = sum(s.montant_total for s in qs)

    return render(request, 'rapports/sorties.html', {
        **ctx_commun(f, societe),
        'lignes': qs,
        'totaux': totaux,
        'titre': 'Sorties',
        'rapport': 'sorties',
        'rapport_icone': 'bi-box-arrow-up',
        'rapport_clr': '#9333ea',
    })


@login_required
def rapport_stock_actuel(request):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    f = get_filtres(request)

    produits_qs = Produit.objects.filter(societe=societe, statut='ACTIF')\
        .select_related('categorie', 'taux_tva')

    if f['produit_id']:
        produits_qs = produits_qs.filter(id=f['produit_id'])

    lignes = []
    total_valeur = Decimal('0')

    for p in produits_qs:
        qte_entree = EntreeStock.objects.filter(societe=societe, produit=p).aggregate(t=Sum('quantite'))['t'] or 0
        qte_sortie = SortieStock.objects.filter(societe=societe, entree_stock__produit=p).aggregate(t=Sum('quantite'))['t'] or 0
        qte_vente  = LigneFacture.objects.filter(facture__societe=societe, produit=p).aggregate(t=Sum('quantite'))['t'] or 0

        stock = qte_entree - qte_sortie - qte_vente

        agg = EntreeStock.objects.filter(societe=societe, produit=p).aggregate(
            total_qte=Sum('quantite'), total_valeur=Sum('prix_revient')
        )

        prix_moyen = (Decimal(agg['total_valeur'] or 0) / Decimal(agg['total_qte'] or 1)) if agg['total_qte'] else Decimal(p.prix_vente or 0)
        valeur_stock = max(stock, 0) * prix_moyen
        total_valeur += valeur_stock

        lignes.append({
            'produit': p,
            'qte_entree': qte_entree,
            'qte_sortie': qte_sortie,
            'qte_vente': qte_vente,
            'stock': stock,
            'prix_moyen': round(float(prix_moyen), 2),
            'valeur_stock': round(float(valeur_stock), 2),
            'alerte': stock <= 0,
        })

    lignes.sort(key=lambda x: x['alerte'], reverse=True)

    return render(request, 'rapports/stock_actuel.html', {
        **ctx_commun(f, societe),
        'lignes': lignes,
        'nb': len(lignes),
        'total_valeur': total_valeur,
        'titre': 'Stock Actuel',
        'rapport': 'stock_actuel',
        'rapport_icone': 'bi-archive',
        'rapport_clr': 'var(--primary)',
    })


@login_required
def rapport_facturation(request):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    f = get_filtres(request)

    qs = Facture.objects.filter(societe=societe).select_related('client').order_by('-date_facture')

    if f['date_debut']:
        qs = qs.filter(date_facture__gte=f['date_debut'])
    if f['date_fin']:
        qs = qs.filter(date_facture__lte=f['date_fin'])
    if f['produit_id']:
        qs = qs.filter(lignes__produit__id=f['produit_id']).distinct()
    if f['service_id']:
        qs = qs.filter(lignes__service__id=f['service_id']).distinct()

    factures_fn = qs.filter(type_facture='FN')
    factures_fa = qs.filter(type_facture='FA')

    totaux_fn = factures_fn.aggregate(
        nb=Count('id'),
        total_ht=Sum('total_ht'),
        total_tva=Sum('total_tva'),
        total_ttc=Sum('total_ttc'),
        nb_clients=Count('client', distinct=True),
    )

    totaux_fa = factures_fa.aggregate(
        total_ht=Sum('total_ht'),
        total_tva=Sum('total_tva'),
        total_ttc=Sum('total_ttc'),
    )

    totaux = {
        'nb': totaux_fn.get('nb') or 0,
        'total_ht': (totaux_fn.get('total_ht') or 0) - (totaux_fa.get('total_ht') or 0),
        'total_tva': (totaux_fn.get('total_tva') or 0) - (totaux_fa.get('total_tva') or 0),
        'total_ttc': (totaux_fn.get('total_ttc') or 0) - (totaux_fa.get('total_ttc') or 0),
        'nb_clients': totaux_fn.get('nb_clients') or 0,
        'nb_avoirs': factures_fa.count(),
        'total_ht_avoirs': totaux_fa.get('total_ht') or 0,
        'total_tva_avoirs': totaux_fa.get('total_tva') or 0,
        'total_ttc_avoirs': totaux_fa.get('total_ttc') or 0,
    }

    return render(request, 'rapports/facturation.html', {
        **ctx_commun(f, societe),
        'factures': qs,
        'totaux': totaux,
        'titre': 'Ventes / Facturation',
        'rapport': 'facturation',
        'rapport_icone': 'bi-receipt',
        'rapport_clr': 'var(--primary)',
    })

@login_required
def export_stock_excel(request):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('rapports:stock_actuel')

    # On récupère les mêmes données que la vue principale
    # (on duplique un peu le code pour l'instant - on pourra factoriser plus tard)
    f = get_filtres(request)
    produits_qs = Produit.objects.filter(societe=societe, statut='ACTIF')

    if f['produit_id']:
        produits_qs = produits_qs.filter(id=f['produit_id'])

    lignes = []
    for p in produits_qs:
        # ... (même calcul que dans rapport_stock_actuel - à factoriser plus tard)
        qte_entree = EntreeStock.objects.filter(societe=societe, produit=p).aggregate(t=Sum('quantite'))['t'] or 0
        qte_sortie = SortieStock.objects.filter(societe=societe, entree_stock__produit=p).aggregate(t=Sum('quantite'))['t'] or 0
        qte_vente  = LigneFacture.objects.filter(facture__societe=societe, produit=p).aggregate(t=Sum('quantite'))['t'] or 0
        stock = qte_entree - qte_sortie - qte_vente

        agg = EntreeStock.objects.filter(societe=societe, produit=p).aggregate(
            total_qte=Sum('quantite'), total_valeur=Sum('prix_revient')
        )
        prix_moyen = (Decimal(agg['total_valeur'] or 0) / Decimal(agg['total_qte'] or 1)) if agg['total_qte'] else Decimal(p.prix_vente or 0)
        valeur_stock = max(stock, 0) * prix_moyen

        lignes.append({
            'produit': p,
            'qte_entree': qte_entree,
            'qte_sortie': qte_sortie,
            'qte_vente': qte_vente,
            'stock': stock,
            'prix_moyen': round(float(prix_moyen), 2),
            'valeur_stock': round(float(valeur_stock), 2),
        })

    colonnes = ['Produit', 'Code', 'Catégorie', 'Unité', 'Entré', 'Sorti', 'Vendu', 'Stock', 'PMP (BIF)', 'Valeur Stock (BIF)']
    data_export = []
    for l in lignes:
        data_export.append([
            l['produit'].designation,
            l['produit'].code,
            getattr(l['produit'].categorie, 'nom', '—'),
            l['produit'].unite or '—',
            l['qte_entree'],
            l['qte_sortie'],
            l['qte_vente'],
            l['stock'],
            l['prix_moyen'],
            l['valeur_stock'],
        ])

    chemin = generer_excel("Stock Actuel", colonnes, data_export, "stock_actuel")

    return redirect(f"/media/{chemin}")


@login_required
def export_stock_pdf(request):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('rapports:stock_actuel')

    f = get_filtres(request)

    produits_qs = Produit.objects.filter(societe=societe, statut='ACTIF')

    if f['produit_id']:
        produits_qs = produits_qs.filter(id=f['produit_id'])

    lignes = []
    for p in produits_qs:
        qte_entree = EntreeStock.objects.filter(societe=societe, produit=p).aggregate(t=Sum('quantite'))['t'] or 0
        qte_sortie = SortieStock.objects.filter(societe=societe, entree_stock__produit=p).aggregate(t=Sum('quantite'))['t'] or 0
        qte_vente  = LigneFacture.objects.filter(facture__societe=societe, produit=p).aggregate(t=Sum('quantite'))['t'] or 0
        stock = qte_entree - qte_sortie - qte_vente

        agg = EntreeStock.objects.filter(societe=societe, produit=p).aggregate(
            total_qte=Sum('quantite'), total_valeur=Sum('prix_revient')
        )
        prix_moyen = (Decimal(agg['total_valeur'] or 0) / Decimal(agg['total_qte'] or 1)) if agg['total_qte'] else Decimal(p.prix_vente or 0)
        valeur_stock = max(stock, 0) * prix_moyen

        lignes.append({
            'produit': p,
            'qte_entree': qte_entree,
            'qte_sortie': qte_sortie,
            'qte_vente': qte_vente,
            'stock': stock,
            'prix_moyen': round(float(prix_moyen), 2),
            'valeur_stock': round(float(valeur_stock), 2),
        })

    # Préparation des données
    colonnes = ['Produit', 'Code', 'Catégorie', 'Unité', 'Entré', 'Sorti', 'Vendu', 'Stock', 'PMP (BIF)', 'Valeur Stock (BIF)']
    data = []
    for l in lignes:
        data.append([
            l['produit'].designation,
            l['produit'].code or '—',
            getattr(l['produit'].categorie, 'nom', '—'),
            l['produit'].unite or '—',
            l['qte_entree'],
            l['qte_sortie'],
            l['qte_vente'],
            l['stock'],
            l['prix_moyen'],
            l['valeur_stock'],
        ])

    # Important : orientation paysage
    chemin = generer_pdf(
        titre="Rapport Stock Actuel", 
        colonnes=colonnes, 
        lignes=data, 
        type_rapport="stock_actuel",
        orientation="landscape"      # ← Correction principale
    )
    return redirect(f"/media/{chemin}")



    # ====================== EXPORT ENTRÉES ======================
@login_required
def export_entrees_excel(request):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('rapports:entrees')

    f = get_filtres(request)

    qs = EntreeStock.objects.filter(societe=societe).select_related(
        'produit', 'produit__categorie', 'fournisseur'
    ).order_by('-date_entree')

    if f['date_debut']:
        qs = qs.filter(date_entree__gte=f['date_debut'])
    if f['date_fin']:
        qs = qs.filter(date_entree__lte=f['date_fin'])
    if f['produit_id']:
        qs = qs.filter(produit__id=f['produit_id'])

    colonnes = ['Date', 'Type', 'Produit', 'Code', 'Catégorie', 'Fournisseur', 'Quantité', 'Prix Revient', 'Montant Total', 'OBR']
    data = []
    for e in qs:
        data.append([
            e.date_entree.strftime('%d/%m/%Y'),
            e.type_entree or '—',
            e.produit.designation,
            e.produit.code or '—',
            getattr(e.produit.categorie, 'nom', '—'),
            getattr(e.fournisseur, 'nom', '—'),
            e.quantite,
            float(e.prix_revient or 0),
            float(e.montant_total or 0),
            e.statut_obr or '—',
        ])

    chemin = generer_excel("Entrées Stock", colonnes, data, "entrees")
    return redirect(f"/media/{chemin}")


@login_required
def export_entrees_pdf(request):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('rapports:entrees')

    f = get_filtres(request)

    qs = EntreeStock.objects.filter(societe=societe).select_related(
        'produit', 'produit__categorie', 'fournisseur'
    ).order_by('-date_entree')

    if f['date_debut']:
        qs = qs.filter(date_entree__gte=f['date_debut'])
    if f['date_fin']:
        qs = qs.filter(date_entree__lte=f['date_fin'])
    if f['produit_id']:
        qs = qs.filter(produit__id=f['produit_id'])

    colonnes = ['Date', 'Type', 'Produit', 'Code', 'Catégorie', 'Fournisseur', 'Quantité', 'Prix Revient', 'Montant Total', 'OBR']
    data = []
    for e in qs:
        data.append([
            e.date_entree.strftime('%d/%m/%Y'),
            e.type_entree or '—',
            e.produit.designation,
            e.produit.code or '—',
            getattr(e.produit.categorie, 'nom', '—'),
            getattr(e.fournisseur, 'nom', '—'),
            e.quantite,
            float(e.prix_revient or 0),
            float(e.montant_total or 0),
            e.statut_obr or '—',
        ])

    # Correction : passage en mode paysage + titre clair
    chemin = generer_pdf(
        titre="Rapport Entrées Stock", 
        colonnes=colonnes, 
        lignes=data, 
        type_rapport="entrees",
        orientation="landscape"      # ← Important pour 10 colonnes
    )
    return redirect(f"/media/{chemin}")

# ══════════════════════════════════════════════
#  EXPORT SORTIES
# ══════════════════════════════════════════════

@login_required
def export_sorties_excel(request):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('rapports:sorties')

    f = get_filtres(request)

    qs = SortieStock.objects.filter(societe=societe).select_related(
        'entree_stock', 'entree_stock__produit', 'entree_stock__produit__categorie'
    ).order_by('-date_sortie')

    if f['date_debut']:
        qs = qs.filter(date_sortie__gte=f['date_debut'])
    if f['date_fin']:
        qs = qs.filter(date_sortie__lte=f['date_fin'])
    if f['produit_id']:
        qs = qs.filter(entree_stock__produit__id=f['produit_id'])

    colonnes = ['Date', 'Type', 'Produit', 'Code', 'Quantité', 'Prix Unitaire', 'Montant Total', 'Commentaire', 'OBR']
    data = []
    for s in qs:
        data.append([
            s.date_sortie.strftime('%d/%m/%Y'),
            s.type_sortie or '—',
            s.entree_stock.produit.designation if s.entree_stock and s.entree_stock.produit else '—',
            s.entree_stock.produit.code if s.entree_stock and s.entree_stock.produit else '—',
            s.quantite,
            float(s.prix or 0),
            float(s.montant_total or 0),
            s.commentaire or '—',
            s.statut_obr or '—',
        ])

    chemin = generer_excel("Sorties Stock", colonnes, data, "sorties")
    return redirect(f"/media/{chemin}")


@login_required
def export_sorties_pdf(request):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('rapports:sorties')

    f = get_filtres(request)

    qs = SortieStock.objects.filter(societe=societe).select_related(
        'entree_stock', 'entree_stock__produit', 'entree_stock__produit__categorie'
    ).order_by('-date_sortie')

    if f['date_debut']:
        qs = qs.filter(date_sortie__gte=f['date_debut'])
    if f['date_fin']:
        qs = qs.filter(date_sortie__lte=f['date_fin'])
    if f['produit_id']:
        qs = qs.filter(entree_stock__produit__id=f['produit_id'])

    colonnes = ['Date', 'Type', 'Produit', 'Code', 'Quantité', 'Prix Unitaire', 'Montant Total', 'Commentaire', 'OBR']
    
    data = []
    for s in qs:
        data.append([
            s.date_sortie.strftime('%d/%m/%Y') if s.date_sortie else '—',  # ✅ sécurité ajoutée
            s.type_sortie or '—',
            s.entree_stock.produit.designation if s.entree_stock and s.entree_stock.produit else '—',
            s.entree_stock.produit.code if s.entree_stock and s.entree_stock.produit else '—',
            s.quantite,
            float(s.prix or 0),
            float(s.montant_total or 0),
            s.commentaire or '—',
            s.statut_obr or '—',
        ])

    # ✅ CORRECTION ICI
    chemin = generer_pdf(
        titre="Rapport Sorties Stock",
        colonnes=colonnes,
        lignes=data,
        type_rapport="sorties",
        orientation="landscape"   # ← AJOUT IMPORTANT
    )

    return redirect(f"/media/{chemin}")


    # ══════════════════════════════════════════════
#  EXPORT FACTURATION
# ══════════════════════════════════════════════

# ══════════════════════════════════════════════
#  EXPORT FACTURATION
# ══════════════════════════════════════════════

@login_required
def export_facturation_excel(request):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('rapports:facturation')

    f = get_filtres(request)

    qs = Facture.objects.filter(societe=societe).select_related('client').order_by('-date_facture')

    if f['date_debut']:
        qs = qs.filter(date_facture__gte=f['date_debut'])
    if f['date_fin']:
        qs = qs.filter(date_facture__lte=f['date_fin'])
    if f['produit_id']:
        qs = qs.filter(lignes__produit__id=f['produit_id']).distinct()
    if f['service_id']:
        qs = qs.filter(lignes__service__id=f['service_id']).distinct()

    colonnes = ['N° Facture', 'Date', 'Client', 'Type', 'Statut', 'Total HT', 'TVA', 'Total TTC', 'OBR']
    data = []
    for facture in qs:
        data.append([
            facture.numero or '—',
            facture.date_facture.strftime('%d/%m/%Y') if facture.date_facture else '—',
            getattr(facture.client, 'nom', '—'),
            facture.get_type_facture_display() or facture.type_facture or '—',
            getattr(facture, 'statut', '—') or '—',                    # ← Correction ici
            float(getattr(facture, 'total_ht', 0) or 0),
            float(getattr(facture, 'total_tva', 0) or 0),
            float(getattr(facture, 'total_ttc', 0) or 0),
            getattr(facture, 'statut_obr', '—') or '—',
        ])

    chemin = generer_excel("Facturation", colonnes, data, "facturation")
    return redirect(f"/media/{chemin}")


@login_required
def export_facturation_pdf(request):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('rapports:facturation')

    f = get_filtres(request)

    qs = Facture.objects.filter(societe=societe).select_related('client').order_by('-date_facture')

    if f['date_debut']:
        qs = qs.filter(date_facture__gte=f['date_debut'])
    if f['date_fin']:
        qs = qs.filter(date_facture__lte=f['date_fin'])
    if f['produit_id']:
        qs = qs.filter(lignes__produit__id=f['produit_id']).distinct()
    if f['service_id']:
        qs = qs.filter(lignes__service__id=f['service_id']).distinct()

    colonnes = ['N° Facture', 'Date', 'Client', 'Type', 'Statut', 'Total HT', 'TVA', 'Total TTC', 'OBR']
    data = []
    for facture in qs:
        data.append([
            facture.numero or '—',
            facture.date_facture.strftime('%d/%m/%Y') if facture.date_facture else '—',
            getattr(facture.client, 'nom', '—'),
            facture.get_type_facture_display() or facture.type_facture or '—',
            getattr(facture, 'statut', '—') or '—',
            float(getattr(facture, 'total_ht', 0) or 0),
            float(getattr(facture, 'total_tva', 0) or 0),
            float(getattr(facture, 'total_ttc', 0) or 0),
            getattr(facture, 'statut_obr', '—') or '—',
        ])

    # Important : on passe orientation="landscape"
    chemin = generer_pdf(
        titre="Rapport Facturation", 
        colonnes=colonnes, 
        lignes=data, 
        type_rapport="facturation",
        orientation="landscape"      # ← Ici le changement
    )
    return redirect(f"/media/{chemin}")



# ══════════════════════════════════════════════
#  EXPORT COÛT DU STOCK VENDU
# ══════════════════════════════════════════════

# ══════════════════════════════════════════════
#  EXPORT COÛT DU STOCK VENDU
# ══════════════════════════════════════════════
# ══════════════════════════════════════════════
#  EXPORT COÛT DU STOCK VENDU
# ══════════════════════════════════════════════

@login_required
def export_cout_stock_excel(request):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('rapports:cout_stock')

    f = get_filtres(request)

    qs = LigneFacture.objects.filter(facture__societe=societe)\
        .select_related('facture', 'facture__client', 'produit', 'service')\
        .order_by('-facture__date_facture')

    if f['date_debut']:
        qs = qs.filter(facture__date_facture__gte=f['date_debut'])
    if f['date_fin']:
        qs = qs.filter(facture__date_facture__lte=f['date_fin'])
    if f['produit_id']:
        qs = qs.filter(produit__id=f['produit_id'])
    if f['service_id']:
        qs = qs.filter(service__id=f['service_id'])

    colonnes = ['Facture', 'Date', 'Client', 'Désignation', 'Type', 'Qté', 'PU HT', 'TVA %', 'Montant HT', 'Montant TTC']
    data = []
    for l in qs:
        designation = (l.produit.designation if l.produit else 
                      (l.service.designation if l.service else getattr(l, 'designation', '—')))

        # Correction du champ prix
        prix_unitaire = getattr(l, 'prix_unitaire_ht', None) or getattr(l, 'prix_unitaire', None) or getattr(l, 'prix_ht', 0)

        data.append([
            l.facture.numero or '—',
            l.facture.date_facture.strftime('%d/%m/%Y') if l.facture.date_facture else '—',
            getattr(l.facture.client, 'nom', '—'),
            designation,
            'Avoir (FA)' if getattr(l.facture, 'type_facture', None) == 'FA' else ('Produit' if l.produit else 'Service'),
            l.quantite or 0,
            float(prix_unitaire or 0),
            l.taux_tva or 0,
            float(getattr(l, 'montant_ht', 0) or 0),
            float(getattr(l, 'montant_ttc', 0) or 0),
        ])

    chemin = generer_excel("Coût du Stock Vendu", colonnes, data, "cout_stock")
    return redirect(f"/media/{chemin}")


@login_required
def export_cout_stock_pdf(request):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('rapports:cout_stock')

    f = get_filtres(request)

    qs = LigneFacture.objects.filter(facture__societe=societe)\
        .select_related('facture', 'facture__client', 'produit', 'service')\
        .order_by('-facture__date_facture')

    if f['date_debut']:
        qs = qs.filter(facture__date_facture__gte=f['date_debut'])
    if f['date_fin']:
        qs = qs.filter(facture__date_facture__lte=f['date_fin'])
    if f['produit_id']:
        qs = qs.filter(produit__id=f['produit_id'])
    if f['service_id']:
        qs = qs.filter(service__id=f['service_id'])

    colonnes = ['Facture', 'Date', 'Client', 'Désignation', 'Type', 'Qté', 'PU HT', 'TVA %', 'Montant HT', 'Montant TTC']
    data = []
    for l in qs:
        designation = (l.produit.designation if l.produit else 
                      (l.service.designation if l.service else getattr(l, 'designation', '—')))

        prix_unitaire = getattr(l, 'prix_unitaire_ht', None) or getattr(l, 'prix_unitaire', None) or getattr(l, 'prix_ht', 0)

        data.append([
            l.facture.numero or '—',
            l.facture.date_facture.strftime('%d/%m/%Y') if l.facture.date_facture else '—',
            getattr(l.facture.client, 'nom', '—'),
            designation,
            'Avoir (FA)' if getattr(l.facture, 'type_facture', None) == 'FA' else ('Produit' if l.produit else 'Service'),
            l.quantite or 0,
            float(prix_unitaire or 0),
            l.taux_tva or 0,
            float(getattr(l, 'montant_ht', 0) or 0),
            float(getattr(l, 'montant_ttc', 0) or 0),
        ])

    chemin = generer_pdf(
        titre="Rapport Coût du Stock Vendu", 
        colonnes=colonnes, 
        lignes=data, 
        type_rapport="cout_stock",
        orientation="landscape"      # Paysage recommandé pour ce rapport
    )
    return redirect(f"/media/{chemin}")
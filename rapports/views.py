from decimal import Decimal, ROUND_DOWN
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
from collections import defaultdict

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


def quantize_3dec(value) -> Decimal:
    """✅ Utilisé partout - 3 décimales sans arrondissement strict"""
    if value is None:
        return Decimal('0.000')
    return Decimal(value).quantize(Decimal('0.001'), rounding=ROUND_DOWN)


def format_titre_avec_dates(titre_base, date_debut, date_fin):
    if not date_debut and not date_fin:
        return titre_base
    
    parts = []
    if date_debut:
        try:
            d = date_debut.split('-')
            parts.append(f"du {d[2]}/{d[1]}/{d[0]}")
        except:
            parts.append(f"du {date_debut}")
    if date_fin:
        try:
            d = date_fin.split('-')
            parts.append(f"au {d[2]}/{d[1]}/{d[0]}")
        except:
            parts.append(f"au {date_fin}")
    
    titre = f"{titre_base} ({' '.join(parts)})"
    # Nettoyage pour Excel (supprime les caractères interdits)
    titre = titre.replace('/', '-').replace('\\', '-')
    
    return titre


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

    if f['date_debut']: qs = qs.filter(date_entree__gte=f['date_debut'])
    if f['date_fin']:   qs = qs.filter(date_entree__lte=f['date_fin'])
    if f['produit_id']: qs = qs.filter(produit__id=f['produit_id'])

    # Calcul par devise
    totaux_par_devise = defaultdict(lambda: {
        'nb': 0,
        'total_qte': Decimal('0'),
        'total_valeur': Decimal('0')
    })

    for e in qs:
        devise = getattr(e.produit, 'devise', 'BIF')
        d = totaux_par_devise[devise]
        d['nb'] += 1
        d['total_qte'] += quantize_3dec(e.quantite or 0)
        d['total_valeur'] += quantize_3dec(e.montant_total or 0)

    return render(request, 'rapports/entrees.html', {
        **ctx_commun(f, societe),
        'lignes': qs,
        'totaux_par_devise': dict(totaux_par_devise),
        'titre': format_titre_avec_dates('Entrées / Achats', f['date_debut'], f['date_fin']),
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

    if f['date_debut']: qs = qs.filter(facture__date_facture__gte=f['date_debut'])
    if f['date_fin']:   qs = qs.filter(facture__date_facture__lte=f['date_fin'])
    if f['produit_id']: qs = qs.filter(produit__id=f['produit_id'])
    if f['service_id']: qs = qs.filter(service__id=f['service_id'])

    ll = list(qs)

    # Calcul par devise
    totaux_par_devise = defaultdict(lambda: {
        'nb': 0, 'total_ht': Decimal('0'), 'total_tva': Decimal('0'), 'total_ttc': Decimal('0')
    })

    for l in ll:
        devise = getattr(l.facture, 'devise', 'BIF') or 'BIF'
        d = totaux_par_devise[devise]
        d['nb'] += 1
        d['total_ht']  += quantize_3dec(getattr(l, 'montant_ht', 0))
        d['total_tva'] += quantize_3dec(getattr(l, 'montant_tva', 0))
        d['total_ttc'] += quantize_3dec(getattr(l, 'montant_ttc', 0))

    total_ht  = sum(d['total_ht'] for d in totaux_par_devise.values())
    total_tva = sum(d['total_tva'] for d in totaux_par_devise.values())
    total_ttc = sum(d['total_ttc'] for d in totaux_par_devise.values())

    return render(request, 'rapports/cout_stock.html', {
        **ctx_commun(f, societe),
        'lignes': ll,
        'nb': len(ll),
        'total_ht': total_ht,
        'total_tva': total_tva,
        'total_ttc': total_ttc,
        'totaux_par_devise': dict(totaux_par_devise),
        'totaux': {'nb_avoirs': sum(1 for l in ll if getattr(l.facture, 'type_facture', None) == 'FA')},
        'titre': format_titre_avec_dates('Coût du Stock Vendu', f['date_debut'], f['date_fin']),
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
        'entree_stock', 'entree_stock__produit'
    ).order_by('-date_sortie')

    if f['date_debut']: qs = qs.filter(date_sortie__gte=f['date_debut'])
    if f['date_fin']:   qs = qs.filter(date_sortie__lte=f['date_fin'])
    if f['produit_id']: qs = qs.filter(entree_stock__produit__id=f['produit_id'])

    # Calcul par devise
    totaux_par_devise = defaultdict(lambda: {
        'nb': 0,
        'total_qte': Decimal('0'),
        'total_valeur': Decimal('0')
    })

    for s in qs:
        produit = s.entree_stock.produit if s.entree_stock else None
        devise = getattr(produit, 'devise', 'BIF') if produit else 'BIF'
        d = totaux_par_devise[devise]
        d['nb'] += 1
        d['total_qte'] += quantize_3dec(s.quantite or 0)
        d['total_valeur'] += quantize_3dec(s.montant_total or 0)

    return render(request, 'rapports/sorties.html', {
        **ctx_commun(f, societe),
        'lignes': qs,
        'totaux_par_devise': dict(totaux_par_devise),
        'titre': format_titre_avec_dates('Sorties', f['date_debut'], f['date_fin']),
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

    # ✅ Totaux par devise au lieu d'un total global sans devise
    totaux_par_devise = defaultdict(lambda: {
        'nb': 0,
        'total_valeur': Decimal('0.000'),
    })

    for p in produits_qs:
        qte_entree = EntreeStock.objects.filter(societe=societe, produit=p).aggregate(t=Sum('quantite'))['t'] or 0
        qte_sortie = SortieStock.objects.filter(societe=societe, entree_stock__produit=p).aggregate(t=Sum('quantite'))['t'] or 0
        qte_vente  = LigneFacture.objects.filter(facture__societe=societe, produit=p).aggregate(t=Sum('quantite'))['t'] or 0

        stock = qte_entree - qte_sortie - qte_vente

        agg = EntreeStock.objects.filter(societe=societe, produit=p).aggregate(
            total_qte=Sum('quantite'), total_valeur=Sum('prix_revient')
        )

        # ✅ quantize_3dec appliqué avant la multiplication, pas seulement après
        prix_moyen = quantize_3dec(
            (Decimal(agg['total_valeur'] or 0) / Decimal(agg['total_qte'] or 1))
            if agg.get('total_qte')
            else Decimal(getattr(p, 'prix_vente', 0) or 0)
        )

        valeur_stock = quantize_3dec(Decimal(max(stock, 0)) * prix_moyen)

        # ✅ Devise réelle du produit, sans fallback BIF automatique
        devise = (p.devise or 'BIF').strip()

        lignes.append({
            'produit': p,
            'qte_entree': qte_entree,
            'qte_sortie': qte_sortie,
            'qte_vente': qte_vente,
            'stock': stock,
            'prix_moyen': prix_moyen,
            'valeur_stock': valeur_stock,
            'devise': devise,
            'alerte': stock <= 0,
        })

        # ✅ Accumulation par devise, pas dans un total global
        totaux_par_devise[devise]['nb'] += 1
        totaux_par_devise[devise]['total_valeur'] += valeur_stock

    lignes.sort(key=lambda x: x['alerte'], reverse=True)

    return render(request, 'rapports/stock_actuel.html', {
        **ctx_commun(f, societe),
        'lignes': lignes,
        'nb': len(lignes),
        # ✅ total_valeur supprimé — remplacé par totaux_par_devise
        'totaux_par_devise': dict(totaux_par_devise),
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

    if f['date_debut']: qs = qs.filter(date_facture__gte=f['date_debut'])
    if f['date_fin']:   qs = qs.filter(date_facture__lte=f['date_fin'])
    if f['produit_id']: qs = qs.filter(lignes__produit__id=f['produit_id']).distinct()
    if f['service_id']: qs = qs.filter(lignes__service__id=f['service_id']).distinct()

    totaux_par_devise = defaultdict(lambda: {
        'nb': 0, 'total_ht': Decimal('0'), 'total_tva': Decimal('0'), 'total_ttc': Decimal('0'), 'nb_clients': 0
    })

    for facture in qs.filter(type_facture='FN'):
        devise = getattr(facture, 'devise', 'BIF') or 'BIF'
        d = totaux_par_devise[devise]
        d['nb'] += 1
        d['total_ht']  += quantize_3dec(facture.total_ht or 0)
        d['total_tva'] += quantize_3dec(facture.total_tva or 0)
        d['total_ttc'] += quantize_3dec(facture.total_ttc or 0)
        if facture.client:
            d['nb_clients'] += 1

    for facture in qs.filter(type_facture='FA'):
        devise = getattr(facture, 'devise', 'BIF') or 'BIF'
        d = totaux_par_devise[devise]
        d['total_ht']  -= quantize_3dec(facture.total_ht or 0)
        d['total_tva'] -= quantize_3dec(facture.total_tva or 0)
        d['total_ttc'] -= quantize_3dec(facture.total_ttc or 0)

    totaux = {
        'par_devise': dict(totaux_par_devise),
        'total_ht': sum(d['total_ht'] for d in totaux_par_devise.values()),
        'total_tva': sum(d['total_tva'] for d in totaux_par_devise.values()),
        'total_ttc': sum(d['total_ttc'] for d in totaux_par_devise.values()),
        'nb': sum(d['nb'] for d in totaux_par_devise.values()),
        'nb_clients': sum(d['nb_clients'] for d in totaux_par_devise.values()),
        'nb_avoirs': qs.filter(type_facture='FA').count(),
    }

    return render(request, 'rapports/facturation.html', {
        **ctx_commun(f, societe),
        'factures': qs,
        'totaux': totaux,
        'titre': format_titre_avec_dates('Ventes / Facturation', f['date_debut'], f['date_fin']),
        'rapport': 'facturation',
        'rapport_icone': 'bi-receipt',
        'rapport_clr': 'var(--primary)',
    })

# ══════════════════════════════════════════════
#  EXPORTS
# ══════════════════════════════════════════════

@login_required
def export_stock_excel(request):
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
        prix_moyen = (Decimal(agg['total_valeur'] or 0) / Decimal(agg['total_qte'] or 1)) if agg.get('total_qte') else Decimal(p.prix_vente or 0)
        valeur_stock = Decimal(max(stock, 0)) * prix_moyen

        lignes.append({
            'produit': p,
            'qte_entree': qte_entree,
            'qte_sortie': qte_sortie,
            'qte_vente': qte_vente,
            'stock': stock,
            'prix_moyen': quantize_3dec(prix_moyen),
            'valeur_stock': quantize_3dec(valeur_stock),
            'devise': p.devise,
        })

    colonnes = ['Produit', 'Code', 'Catégorie', 'Unité', 'Entré', 'Sorti', 'Vendu', 'Stock', 
                'PMP', 'Valeur Stock', 'Devise']
    
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
            l['devise'],
        ])

    titre = format_titre_avec_dates("Stock Actuel", f['date_debut'], f['date_fin'])
    chemin = generer_excel(titre, colonnes, data_export, "stock_actuel",date_debut=f['date_debut'],   # ← Ajout important
        date_fin=f['date_fin'] )
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
        prix_moyen = (Decimal(agg['total_valeur'] or 0) / Decimal(agg['total_qte'] or 1)) if agg.get('total_qte') else Decimal(p.prix_vente or 0)
        valeur_stock = Decimal(max(stock, 0)) * prix_moyen

        lignes.append({
            'produit': p,
            'qte_entree': qte_entree,
            'qte_sortie': qte_sortie,
            'qte_vente': qte_vente,
            'stock': stock,
            'prix_moyen': quantize_3dec(prix_moyen),
            'valeur_stock': quantize_3dec(valeur_stock),
            'devise': p.devise,
        })

    colonnes = ['Produit', 'Code', 'Catégorie', 'Unité', 'Entré', 'Sorti', 'Vendu', 'Stock', 
                'PMP', 'Valeur Stock', 'Devise']
    
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
            l['devise'],
        ])

    titre = format_titre_avec_dates("Rapport Stock Actuel", f['date_debut'], f['date_fin'])
    chemin = generer_pdf(
        titre=titre, 
        colonnes=colonnes, 
        lignes=data, 
        type_rapport="stock_actuel",
        orientation="landscape",
        date_debut=f['date_debut'],   # ← Ajout important
        date_fin=f['date_fin'] 
    )
    return redirect(f"/media/{chemin}")


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

    if f['date_debut']: qs = qs.filter(date_entree__gte=f['date_debut'])
    if f['date_fin']:   qs = qs.filter(date_entree__lte=f['date_fin'])
    if f['produit_id']: qs = qs.filter(produit__id=f['produit_id'])

    colonnes = ['Date', 'Type', 'Produit', 'Code', 'Catégorie', 'Fournisseur', 'Quantité', 
                'Prix Revient', 'Montant Total', 'Devise', 'OBR']
    
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
            quantize_3dec(e.prix_revient or 0),
            quantize_3dec(e.montant_total or 0),
            getattr(e.produit, 'devise', 'BIF'),
            e.statut_obr or '—',
        ])

        titre = format_titre_avec_dates("Entrées Stock", f['date_debut'], f['date_fin'])
    
        chemin = generer_excel(
            titre, 
            colonnes, 
            data, 
            "entrees",
            date_debut=f['date_debut'],
            date_fin=f['date_fin']
        )
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

    if f['date_debut']: qs = qs.filter(date_entree__gte=f['date_debut'])
    if f['date_fin']:   qs = qs.filter(date_entree__lte=f['date_fin'])
    if f['produit_id']: qs = qs.filter(produit__id=f['produit_id'])

    colonnes = ['Date', 'Type', 'Produit', 'Code', 'Catégorie', 'Fournisseur', 'Quantité', 
                'Prix Revient', 'Montant Total', 'Devise', 'OBR']
    
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
            quantize_3dec(e.prix_revient or 0),
            quantize_3dec(e.montant_total or 0),
            getattr(e.produit, 'devise', 'BIF'),
            e.statut_obr or '—',
        ])

    titre = format_titre_avec_dates("Rapport Entrées Stock", f['date_debut'], f['date_fin'])
    chemin = generer_pdf(
        titre=titre, 
        colonnes=colonnes, 
        lignes=data, 
        type_rapport="entrees",
        orientation="landscape",
        date_debut=f['date_debut'],   # ← Ajout important
        date_fin=f['date_fin']
    )
    return redirect(f"/media/{chemin}")


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

    if f['date_debut']: qs = qs.filter(date_sortie__gte=f['date_debut'])
    if f['date_fin']:   qs = qs.filter(date_sortie__lte=f['date_fin'])
    if f['produit_id']: qs = qs.filter(entree_stock__produit__id=f['produit_id'])

    colonnes = ['Date', 'Type', 'Produit', 'Code', 'Quantité', 'Prix Unitaire', 'Montant Total', 'Commentaire', 'Devise', 'OBR']
    
    data = []
    for s in qs:
        produit = s.entree_stock.produit if s.entree_stock else None
        data.append([
            s.date_sortie.strftime('%d/%m/%Y') if s.date_sortie else '—',
            s.type_sortie or '—',
            produit.designation if produit else '—',
            produit.code if produit else '—',
            s.quantite,
            quantize_3dec(s.prix or 0),
            quantize_3dec(s.montant_total or 0),
            s.commentaire or '—',
            getattr(produit, 'devise', 'BIF') if produit else 'BIF',
            s.statut_obr or '—',
        ])

    titre = format_titre_avec_dates("Sorties Stock", f['date_debut'], f['date_fin'])
    chemin = generer_excel(titre, colonnes, data, "sorties",date_debut=f['date_debut'],
        date_fin=f['date_fin'])
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

    if f['date_debut']: qs = qs.filter(date_sortie__gte=f['date_debut'])
    if f['date_fin']:   qs = qs.filter(date_sortie__lte=f['date_fin'])
    if f['produit_id']: qs = qs.filter(entree_stock__produit__id=f['produit_id'])

    colonnes = ['Date', 'Type', 'Produit', 'Code', 'Quantité', 'Prix Unitaire', 'Montant Total', 'Commentaire', 'Devise', 'OBR']
    
    data = []
    for s in qs:
        produit = s.entree_stock.produit if s.entree_stock else None
        data.append([
            s.date_sortie.strftime('%d/%m/%Y') if s.date_sortie else '—',
            s.type_sortie or '—',
            produit.designation if produit else '—',
            produit.code if produit else '—',
            s.quantite,
            quantize_3dec(s.prix or 0),
            quantize_3dec(s.montant_total or 0),
            s.commentaire or '—',
            getattr(produit, 'devise', 'BIF') if produit else 'BIF',
            s.statut_obr or '—',
        ])

    titre = format_titre_avec_dates("Rapport Sorties Stock", f['date_debut'], f['date_fin'])
    chemin = generer_pdf(
        titre=titre,
        colonnes=colonnes,
        lignes=data,
        type_rapport="sorties",
        orientation="landscape"
    )
    return redirect(f"/media/{chemin}")


@login_required
def export_facturation_excel(request):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('rapports:facturation')

    f = get_filtres(request)

    qs = Facture.objects.filter(societe=societe).select_related('client').order_by('-date_facture')

    if f['date_debut']: qs = qs.filter(date_facture__gte=f['date_debut'])
    if f['date_fin']:   qs = qs.filter(date_facture__lte=f['date_fin'])
    if f['produit_id']: qs = qs.filter(lignes__produit__id=f['produit_id']).distinct()
    if f['service_id']: qs = qs.filter(lignes__service__id=f['service_id']).distinct()

    colonnes = ['N° Facture', 'Date', 'Client', 'Type', 'Statut', 'Total HT', 'TVA', 'Total TTC', 'Devise', 'OBR']
    data = []
    for facture in qs:
        data.append([
            facture.numero or '—',
            facture.date_facture.strftime('%d/%m/%Y') if facture.date_facture else '—',
            getattr(facture.client, 'nom', '—'),
            facture.get_type_facture_display() or facture.type_facture or '—',
            getattr(facture, 'statut', '—') or '—',
            quantize_3dec(getattr(facture, 'total_ht', 0)),
            quantize_3dec(getattr(facture, 'total_tva', 0)),
            quantize_3dec(getattr(facture, 'total_ttc', 0)),
            getattr(facture, 'devise', 'BIF'),
            getattr(facture, 'statut_obr', '—') or '—',
        ])

    titre = format_titre_avec_dates("Facturation", f['date_debut'], f['date_fin'])
    chemin = generer_excel(titre, colonnes, data, "facturation",date_debut=f['date_debut'],   # ← Ajout important
        date_fin=f['date_fin'] )
    return redirect(f"/media/{chemin}")


@login_required
def export_facturation_pdf(request):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('rapports:facturation')

    f = get_filtres(request)

    qs = Facture.objects.filter(societe=societe).select_related('client').order_by('-date_facture')

    if f['date_debut']: qs = qs.filter(date_facture__gte=f['date_debut'])
    if f['date_fin']:   qs = qs.filter(date_facture__lte=f['date_fin'])
    if f['produit_id']: qs = qs.filter(lignes__produit__id=f['produit_id']).distinct()
    if f['service_id']: qs = qs.filter(lignes__service__id=f['service_id']).distinct()

    colonnes = ['N° Facture', 'Date', 'Client', 'Type', 'Statut', 'Total HT', 'TVA', 'Total TTC', 'Devise', 'OBR']
    data = []
    for facture in qs:
        data.append([
            facture.numero or '—',
            facture.date_facture.strftime('%d/%m/%Y') if facture.date_facture else '—',
            getattr(facture.client, 'nom', '—'),
            facture.get_type_facture_display() or facture.type_facture or '—',
            getattr(facture, 'statut', '—') or '—',
            quantize_3dec(getattr(facture, 'total_ht', 0)),
            quantize_3dec(getattr(facture, 'total_tva', 0)),
            quantize_3dec(getattr(facture, 'total_ttc', 0)),
            getattr(facture, 'devise', 'BIF'),
            getattr(facture, 'statut_obr', '—') or '—',
        ])

    titre = format_titre_avec_dates("Rapport Facturation", f['date_debut'], f['date_fin'])
    chemin = generer_pdf(
        titre=titre, 
        colonnes=colonnes, 
        lignes=data, 
        type_rapport="facturation",
        orientation="landscape",
        date_debut=f['date_debut'],   # ← Ajout important
        date_fin=f['date_fin'] 
    )
    return redirect(f"/media/{chemin}")


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

    if f['date_debut']: qs = qs.filter(facture__date_facture__gte=f['date_debut'])
    if f['date_fin']:   qs = qs.filter(facture__date_facture__lte=f['date_fin'])
    if f['produit_id']: qs = qs.filter(produit__id=f['produit_id'])
    if f['service_id']: qs = qs.filter(service__id=f['service_id'])

    colonnes = ['Facture', 'Date', 'Client', 'Désignation', 'Type', 'Qté', 'PU HT', 'TVA %', 
                'Montant HT', 'Montant TTC', 'Devise']
    
    data = []
    for l in qs:
        designation = (l.produit.designation if l.produit else 
                      (l.service.designation if l.service else getattr(l, 'designation', '—')))
        prix_unitaire = getattr(l, 'prix_unitaire_ht', None) or getattr(l, 'prix_unitaire', None) or getattr(l, 'prix_ht', 0)
        devise = getattr(l.facture, 'devise', 'BIF')

        data.append([
            l.facture.numero or '—',
            l.facture.date_facture.strftime('%d/%m/%Y') if l.facture.date_facture else '—',
            getattr(l.facture.client, 'nom', '—'),
            designation,
            'Avoir (FA)' if getattr(l.facture, 'type_facture', None) == 'FA' else ('Produit' if l.produit else 'Service'),
            l.quantite or 0,
            quantize_3dec(prix_unitaire),
            l.taux_tva or 0,
            quantize_3dec(getattr(l, 'montant_ht', 0)),
            quantize_3dec(getattr(l, 'montant_ttc', 0)),
            devise,
        ])

    titre = format_titre_avec_dates("Coût du Stock Vendu", f['date_debut'], f['date_fin'])
    chemin = generer_excel(titre, colonnes, data, "cout_stock",date_debut=f['date_debut'],   # ← Ajout important
        date_fin=f['date_fin']  )
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

    if f['date_debut']: qs = qs.filter(facture__date_facture__gte=f['date_debut'])
    if f['date_fin']:   qs = qs.filter(facture__date_facture__lte=f['date_fin'])
    if f['produit_id']: qs = qs.filter(produit__id=f['produit_id'])
    if f['service_id']: qs = qs.filter(service__id=f['service_id'])

    colonnes = ['Facture', 'Date', 'Client', 'Désignation', 'Type', 'Qté', 'PU HT', 'TVA %', 
                'Montant HT', 'Montant TTC', 'Devise']
    
    data = []
    for l in qs:
        designation = (l.produit.designation if l.produit else 
                      (l.service.designation if l.service else getattr(l, 'designation', '—')))
        prix_unitaire = getattr(l, 'prix_unitaire_ht', None) or getattr(l, 'prix_unitaire', None) or getattr(l, 'prix_ht', 0)
        devise = getattr(l.facture, 'devise', 'BIF')

        data.append([
            l.facture.numero or '—',
            l.facture.date_facture.strftime('%d/%m/%Y') if l.facture.date_facture else '—',
            getattr(l.facture.client, 'nom', '—'),
            designation,
            'Avoir (FA)' if getattr(l.facture, 'type_facture', None) == 'FA' else ('Produit' if l.produit else 'Service'),
            l.quantite or 0,
            quantize_3dec(prix_unitaire),
            l.taux_tva or 0,
            quantize_3dec(getattr(l, 'montant_ht', 0)),
            quantize_3dec(getattr(l, 'montant_ttc', 0)),
            devise,
        ])

    titre = format_titre_avec_dates("Rapport Coût du Stock Vendu", f['date_debut'], f['date_fin'])
    chemin = generer_pdf(
        titre=titre, 
        colonnes=colonnes, 
        lignes=data, 
        type_rapport="cout_stock",
        orientation="landscape",
        date_debut=f['date_debut'],   # ← Ajout important
        date_fin=f['date_fin'] 
    )
    return redirect(f"/media/{chemin}")
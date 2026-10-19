import os
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
from django.conf import settings
from django.http import FileResponse, Http404
from decimal import Decimal, ROUND_DOWN
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
    mode = request.GET.get('mode')
    if mode is None:
        societe = getattr(request.user, 'societe', None)
        if societe:
            mode = 'PRODUCTION' if societe.obr_mode_production else 'TEST'
        else:
            mode = ''
    return {
        'date_debut': request.GET.get('date_debut', ''),
        'date_fin':   request.GET.get('date_fin', ''),
        'produit_id': request.GET.get('produit', ''),
        'service_id': request.GET.get('service', ''),
        'mode':       mode,
    }


def ctx_commun(f, societe):
    return {
        **f,
        'produits': Produit.objects.filter(societe=societe, statut='ACTIF').order_by('designation'),
        'services': Service.objects.filter(societe=societe, statut='ACTIF').order_by('designation'),
    }

def _reponse_fichier(chemin_relatif):
    chemin_absolu = os.path.join(settings.MEDIA_ROOT, chemin_relatif)
    if not os.path.exists(chemin_absolu):
        raise Http404("Fichier de rapport introuvable.")
    return FileResponse(open(chemin_absolu, 'rb'), as_attachment=True, filename=os.path.basename(chemin_absolu))


def filtrer_par_mode(qs, mode, facture_field=None):
    """Filtre un queryset par mode OBR (TEST/PRODUCTION).
    facture_field : pour les modèles liés à Facture via une FK (ex: 'facture__obr_mode_envoye')"""
    if mode == 'TEST':
        return qs.filter(**{f'{facture_field}obr_mode_envoye': False}) if facture_field else qs.filter(obr_mode_envoye=False)
    elif mode == 'PRODUCTION':
        return qs.filter(**{f'{facture_field}obr_mode_envoye': True}) if facture_field else qs.filter(obr_mode_envoye=True)
    return qs


# ══════════════════════════════════════════════
#  RAPPORT FACTURATION — 22 colonnes niveau ligne (ref. Excel)
# ══════════════════════════════════════════════
COLONNES_FACTURATION = ['No.', 'Numero', 'Type de factures', 'Type de paiement', 'Status', 'Code', 'Produit', 'Qtés', 'P.U HTT', 'TC', 'PHTVA', 'TVA', 'PTVAC', 'PF', 'OTT', 'TSCE', 'TOTAL', 'Date', 'Auteur', 'Client', 'NIF du Client', 'Devise']

STATUT_FACTURATION_LABELS = {'ENVOYE': 'Valide', 'EN_ATTENTE': 'En attente', 'ECHEC': 'Échec', 'ANNULE': 'Annulé'}


def _dec(value):
    try:
        return Decimal(str(value or 0))
    except Exception:
        return Decimal('0')


def _lignes_rapport_facturation(qs):
    """Lignes à plat (1 ligne = 1 ligne de facture) avec vraies valeurs.
    FA en négatif pour des totaux nets. TC/PF/OTT/TSCE à 0 tant que non tarifés."""
    rows = []
    tot = {'qte': Decimal('0'), 'tc': Decimal('0'), 'phtva': Decimal('0'), 'tva': Decimal('0'), 'ptvac': Decimal('0'), 'pfl': Decimal('0'), 'ott': Decimal('0'), 'tsce': Decimal('0'), 'total': Decimal('0')}
    n = 0
    for fact in qs:
        signe = -1 if getattr(fact, 'type_facture', '') == 'FA' else 1
        statut = STATUT_FACTURATION_LABELS.get(getattr(fact, 'statut_obr', ''), getattr(fact, 'statut_obr', '—') or '—')
        try:
            date_txt = fact.date_facture.strftime('%Y-%m-%d') if fact.date_facture else ''
            heure_txt = fact.heure_facture.strftime('%H:%M:%S') if fact.heure_facture else ''
            date_heure = f"{date_txt} {heure_txt}".strip()
        except Exception:
            date_heure = ''
        cp = getattr(fact, 'cree_par', None)
        auteur = getattr(cp, 'nom_complet', None) or getattr(cp, 'username', None) or '—'
        client = getattr(fact, 'client', None)
        for ligne in getattr(fact, 'lignes', []).all() if hasattr(getattr(fact, 'lignes', []), 'all') else []:
            n += 1
            pu = _dec(getattr(ligne, 'prix_unitaire_ht', 0))
            qte = _dec(getattr(ligne, 'quantite', 0))
            tc = _dec(getattr(ligne, 'montant_ct', 0))
            phtva = _dec(getattr(ligne, 'montant_ht', 0))
            tva = _dec(getattr(ligne, 'montant_tva', 0))
            ptvac = _dec(getattr(ligne, 'montant_ttc', 0))
            pfl = _dec(getattr(ligne, 'montant_tl', 0))
            ott = Decimal('0')
            tsce = Decimal('0')
            total = ptvac + pfl
            if signe < 0:
                qte = -qte; tc = -tc; phtva = -phtva; tva = -tva; ptvac = -ptvac; pfl = -pfl; total = -total
            for k, v in (('qte', qte), ('tc', tc), ('phtva', phtva), ('tva', tva), ('ptvac', ptvac), ('pfl', pfl), ('ott', ott), ('tsce', tsce), ('total', total)):
                tot[k] += v
            produit = getattr(ligne, 'produit', None)
            service = getattr(ligne, 'service', None)
            code = getattr(produit, 'code', None) or getattr(service, 'code', None) or '—'
            rows.append({
                'no': n,
                'numero': getattr(fact, 'numero', '—') or '—',
                'type_facture': fact.get_type_facture_display() if hasattr(fact, 'get_type_facture_display') else getattr(fact, 'type_facture', '—'),
                'paiement': fact.get_mode_paiement_display() if hasattr(fact, 'get_mode_paiement_display') else getattr(fact, 'mode_paiement', '—'),
                'statut': statut,
                'code': code,
                'produit': getattr(ligne, 'designation', '—') or '—',
                'qte': float(qte), 'pu': float(pu), 'tc': float(tc), 'phtva': float(phtva), 'tva': float(tva),
                'ptvac': float(ptvac), 'pfl': float(pfl), 'ott': float(ott), 'tsce': float(tsce), 'total': float(total),
                'date': date_heure,
                'auteur': auteur,
                'client': getattr(client, 'nom', '—') or '—',
                'nif_client': getattr(client, 'nif', '',) or '',
                'devise': getattr(fact, 'devise', '') or '',
            })
    return rows, tot


def _row_rapport_facturation(r):
    return [r['no'], r['numero'], r['type_facture'], r['paiement'], r['statut'], r['code'], r['produit'], r['qte'], r['pu'], r['tc'], r['phtva'], r['tva'], r['ptvac'], r['pfl'], r['ott'], r['tsce'], r['total'], r['date'], r['auteur'], r['client'], r['nif_client'], r['devise']]


def _totaux_row_rapport_facturation(tot):
    return ['', '', '', '', '', '', 'TOTAUX', float(tot['qte']), '', float(tot['tc']), float(tot['phtva']), float(tot['tva']), float(tot['ptvac']), float(tot['pfl']), float(tot['ott']), float(tot['tsce']), float(tot['total']), '', '', '', '', '']


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
    
    qs = filtrer_par_mode(qs, f['mode'])

    totaux = qs.aggregate(nb=Count('id'), total_qte=Sum('quantite'))
    totaux['total_valeur'] = sum(e.montant_total for e in qs)

    totaux_par_devise = {}
    for e in qs:
        d = e.produit.devise or 'BIF'
        if d not in totaux_par_devise:
            totaux_par_devise[d] = {'nb': 0, 'total_qte': Decimal('0'), 'total_valeur': Decimal('0')}
        totaux_par_devise[d]['nb'] += 1
        totaux_par_devise[d]['total_qte'] += Decimal(str(e.quantite or 0))
        totaux_par_devise[d]['total_valeur'] += Decimal(str(e.montant_total or 0))

    return render(request, 'rapports/entrees.html', {
        **ctx_commun(f, societe),
        'lignes': qs,
        'totaux': totaux,
        'totaux_par_devise': totaux_par_devise,
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

    qs = filtrer_par_mode(qs, f['mode'], facture_field='facture__')

    ll = list(qs)

    totaux_par_devise = {}
    for l in ll:
        d = l.facture.devise or 'BIF'
        if d not in totaux_par_devise:
            totaux_par_devise[d] = {'total_ht': Decimal('0'), 'total_tva': Decimal('0'), 'total_ttc': Decimal('0')}
        totaux_par_devise[d]['total_ht'] += Decimal(str(l.montant_ht or 0))
        totaux_par_devise[d]['total_tva'] += Decimal(str(l.montant_tva or 0))
        totaux_par_devise[d]['total_ttc'] += Decimal(str(l.montant_ttc or 0))

    return render(request, 'rapports/cout_stock.html', {
        **ctx_commun(f, societe),
        'lignes': ll,
        'nb': len(ll),
        'total_ht': sum(l.montant_ht for l in ll),
        'total_tva': sum(l.montant_tva for l in ll),
        'total_ttc': sum(l.montant_ttc for l in ll),
        'totaux_par_devise': totaux_par_devise,
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

    qs = filtrer_par_mode(qs, f['mode'])

    totaux = qs.aggregate(nb=Count('id'), total_qte=Sum('quantite'))
    totaux['total_valeur'] = sum(s.montant_total for s in qs)

    totaux_par_devise = {}
    for s in qs:
        d = s.entree_stock.produit.devise or 'BIF'
        if d not in totaux_par_devise:
            totaux_par_devise[d] = {'nb': 0, 'total_qte': Decimal('0'), 'total_valeur': Decimal('0')}
        totaux_par_devise[d]['nb'] += 1
        totaux_par_devise[d]['total_qte'] += Decimal(str(s.quantite or 0))
        totaux_par_devise[d]['total_valeur'] += Decimal(str(s.montant_total or 0))

    return render(request, 'rapports/sorties.html', {
        **ctx_commun(f, societe),
        'lignes': qs,
        'totaux': totaux,
        'totaux_par_devise': totaux_par_devise,
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

    produits_qs = filtrer_par_mode(produits_qs, f['mode'])

    lignes = []

    statuts_confirmes = ['ENVOYE', 'VALIDE']

    mode_production = societe.obr_mode_production
    for p in produits_qs:
        qte_entree = EntreeStock.objects.filter(societe=societe, produit=p, statut_obr__in=statuts_confirmes, obr_mode_envoye=mode_production).aggregate(t=Sum('quantite'))['t'] or 0
        qte_sortie = SortieStock.objects.filter(societe=societe, entree_stock__produit=p, statut_obr__in=statuts_confirmes, obr_mode_envoye=mode_production).aggregate(t=Sum('quantite'))['t'] or 0

        stock = qte_entree - qte_sortie

        agg = EntreeStock.objects.filter(societe=societe, produit=p, statut_obr__in=statuts_confirmes, obr_mode_envoye=mode_production).aggregate(
            total_qte=Sum('quantite'), total_valeur=Sum('prix_revient')
        )

        prix_moyen = (Decimal(agg['total_valeur'] or 0) / Decimal(agg['total_qte'] or 1)) if agg['total_qte'] else Decimal(p.prix_vente or 0)
        valeur_stock = max(stock, 0) * prix_moyen

        lignes.append({
            'produit': p,
            'qte_entree': qte_entree,
            'qte_sortie': qte_sortie,
            'stock': stock,
            'prix_moyen': prix_moyen,
            'valeur_stock': valeur_stock,
            'alerte': stock <= 0,
            'devise': p.devise,
        })

    lignes.sort(key=lambda x: x['alerte'], reverse=True)

    totaux_par_devise = {}
    for l in lignes:
        d = l['devise'] or 'BIF'
        if d not in totaux_par_devise:
            totaux_par_devise[d] = {'total_valeur': Decimal('0')}
        totaux_par_devise[d]['total_valeur'] += l['valeur_stock']

    return render(request, 'rapports/stock_actuel.html', {
        **ctx_commun(f, societe),
        'lignes': lignes,
        'nb': len(lignes),
        'totaux_par_devise': totaux_par_devise,
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

    qs = Facture.objects.filter(societe=societe).select_related('client', 'cree_par').prefetch_related('lignes__produit', 'lignes__service').order_by('-date_facture')

    if f['date_debut']:
        qs = qs.filter(date_facture__gte=f['date_debut'])
    if f['date_fin']:
        qs = qs.filter(date_facture__lte=f['date_fin'])
    if f['produit_id']:
        qs = qs.filter(lignes__produit__id=f['produit_id']).distinct()
    if f['service_id']:
        qs = qs.filter(lignes__service__id=f['service_id']).distinct()
    qs = filtrer_par_mode(qs, f['mode'])

    qs_totaux = qs.exclude(statut_obr='ANNULE')
    factures_fn = qs_totaux.filter(type_facture='FN')
    factures_fa = qs_totaux.filter(type_facture='FA')

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
        'par_devise': {},
    }

    show_tc = bool(getattr(societe, 'assujeti_tc', False))
    show_pfl = bool(getattr(societe, 'assujeti_pfl', False))
    totaux['total_tc'] = Decimal('0')
    totaux['total_pfl'] = Decimal('0')
    for fact in qs_totaux:
        d = fact.devise or 'BIF'
        if d not in totaux['par_devise']:
            totaux['par_devise'][d] = {'total_ht': Decimal('0'), 'total_tva': Decimal('0'), 'total_ttc': Decimal('0'), 'total_tc': Decimal('0'), 'total_pfl': Decimal('0')}
        tc = sum((getattr(l, 'montant_ct', 0) or 0) for l in fact.lignes.all()) if show_tc else Decimal('0')
        pfl = sum((getattr(l, 'montant_tl', 0) or 0) for l in fact.lignes.all()) if show_pfl else Decimal('0')
        try:
            tc = Decimal(str(tc or 0))
        except Exception:
            tc = Decimal('0')
        try:
            pfl = Decimal(str(pfl or 0))
        except Exception:
            pfl = Decimal('0')
        if fact.type_facture == 'FA':
            tc = -tc
            pfl = -pfl
        totaux['total_tc'] += tc
        totaux['total_pfl'] += pfl
        if fact.type_facture == 'FN':
            totaux['par_devise'][d]['total_ht'] += fact.total_ht or 0
            totaux['par_devise'][d]['total_tva'] += fact.total_tva or 0
            totaux['par_devise'][d]['total_ttc'] += fact.total_ttc or 0
            totaux['par_devise'][d]['total_tc'] += tc
            totaux['par_devise'][d]['total_pfl'] += pfl
        elif fact.type_facture == 'FA':
            totaux['par_devise'][d]['total_ht'] -= fact.total_ht or 0
            totaux['par_devise'][d]['total_tva'] -= fact.total_tva or 0
            totaux['par_devise'][d]['total_ttc'] -= fact.total_ttc or 0
            totaux['par_devise'][d]['total_tc'] += tc
            totaux['par_devise'][d]['total_pfl'] += pfl

    if show_tc or show_pfl:
        for fact in qs:
            tc = sum((getattr(l, 'montant_ct', 0) or 0) for l in fact.lignes.all()) if show_tc else Decimal('0')
            pfl = sum((getattr(l, 'montant_tl', 0) or 0) for l in fact.lignes.all()) if show_pfl else Decimal('0')
            try:
                fact._tc = Decimal(str(tc or 0))
            except Exception:
                fact._tc = Decimal('0')
            try:
                fact._pfl = Decimal(str(pfl or 0))
            except Exception:
                fact._pfl = Decimal('0')
            if fact.type_facture == 'FA':
                fact._tc = -fact._tc
                fact._pfl = -fact._pfl

    lignes_rapport, tot_lignes = _lignes_rapport_facturation(qs_totaux)

    return render(request, 'rapports/facturation.html', {
        **ctx_commun(f, societe),
        'societe': societe,
        'factures': qs,
        'lignes_rapport': lignes_rapport,
        'tot_lignes': tot_lignes,
        'colonnes_facturation': COLONNES_FACTURATION,
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
    
    produits_qs = filtrer_par_mode(produits_qs, f['mode'])

    mode_production = societe.obr_mode_production
    statuts_confirmes = ['ENVOYE', 'VALIDE']
    lignes = []
    for p in produits_qs:
        qte_entree = EntreeStock.objects.filter(societe=societe, produit=p, statut_obr__in=statuts_confirmes, obr_mode_envoye=mode_production).aggregate(t=Sum('quantite'))['t'] or 0
        qte_sortie = SortieStock.objects.filter(societe=societe, entree_stock__produit=p, statut_obr__in=statuts_confirmes, obr_mode_envoye=mode_production).aggregate(t=Sum('quantite'))['t'] or 0
        stock = qte_entree - qte_sortie

        agg = EntreeStock.objects.filter(societe=societe, produit=p, statut_obr__in=statuts_confirmes, obr_mode_envoye=mode_production).aggregate(
            total_qte=Sum('quantite'), total_valeur=Sum('prix_revient')
        )
        prix_moyen = (Decimal(agg['total_valeur'] or 0) / Decimal(agg['total_qte'] or 1)) if agg['total_qte'] else Decimal(p.prix_vente or 0)
        valeur_stock = max(stock, 0) * prix_moyen

        lignes.append({
            'produit': p,
            'qte_entree': qte_entree,
            'qte_sortie': qte_sortie,
            'stock': stock,
            'prix_moyen': float(Decimal(str(prix_moyen)).quantize(Decimal('0.001'), rounding=ROUND_DOWN)),
            'valeur_stock': float(Decimal(str(valeur_stock)).quantize(Decimal('0.001'), rounding=ROUND_DOWN)),
        })

    colonnes = ['Produit', 'Code', 'Catégorie', 'Unité', 'Entré', 'Sorti', 'Stock', 'PMP (BIF)', 'Valeur Stock (BIF)']
    data_export = []
    for l in lignes:
        data_export.append([
            l['produit'].designation,
            l['produit'].code,
            getattr(l['produit'].categorie, 'nom', '—'),
            l['produit'].unite or '—',
            l['qte_entree'],
            l['qte_sortie'],
            l['stock'],
            l['prix_moyen'],
            l['valeur_stock'],
        ])

    chemin = generer_excel("Stock Actuel", colonnes, data_export, "stock_actuel")

    return _reponse_fichier(chemin)


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

    produits_qs = filtrer_par_mode(produits_qs, f['mode'])

    mode_production = societe.obr_mode_production
    statuts_confirmes = ['ENVOYE', 'VALIDE']
    lignes = []
    for p in produits_qs:
        qte_entree = EntreeStock.objects.filter(societe=societe, produit=p, statut_obr__in=statuts_confirmes, obr_mode_envoye=mode_production).aggregate(t=Sum('quantite'))['t'] or 0
        qte_sortie = SortieStock.objects.filter(societe=societe, entree_stock__produit=p, statut_obr__in=statuts_confirmes, obr_mode_envoye=mode_production).aggregate(t=Sum('quantite'))['t'] or 0
        stock = qte_entree - qte_sortie

        agg = EntreeStock.objects.filter(societe=societe, produit=p, statut_obr__in=statuts_confirmes, obr_mode_envoye=mode_production).aggregate(
            total_qte=Sum('quantite'), total_valeur=Sum('prix_revient')
        )
        prix_moyen = (Decimal(agg['total_valeur'] or 0) / Decimal(agg['total_qte'] or 1)) if agg['total_qte'] else Decimal(p.prix_vente or 0)
        valeur_stock = max(stock, 0) * prix_moyen

        lignes.append({
            'produit': p,
            'qte_entree': qte_entree,
            'qte_sortie': qte_sortie,
            'stock': stock,
            'prix_moyen': float(Decimal(str(prix_moyen)).quantize(Decimal('0.001'), rounding=ROUND_DOWN)),
            'valeur_stock': float(Decimal(str(valeur_stock)).quantize(Decimal('0.001'), rounding=ROUND_DOWN)),
        })

    # Préparation des données
    colonnes = ['Produit', 'Code', 'Catégorie', 'Unité', 'Entré', 'Sorti', 'Stock', 'PMP (BIF)', 'Valeur Stock (BIF)']
    data = []
    for l in lignes:
        data.append([
            l['produit'].designation,
            l['produit'].code or '—',
            getattr(l['produit'].categorie, 'nom', '—'),
            l['produit'].unite or '—',
            l['qte_entree'],
            l['qte_sortie'],
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
    return _reponse_fichier(chemin)



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
    
    qs = filtrer_par_mode(qs, f['mode'])

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
    return _reponse_fichier(chemin)


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
    
    qs = filtrer_par_mode(qs, f['mode'])

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
    return _reponse_fichier(chemin)

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

    qs = filtrer_par_mode(qs, f['mode'])

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
    return _reponse_fichier(chemin)


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

    qs = filtrer_par_mode(qs, f['mode'])

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

    return _reponse_fichier(chemin)


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

    qs = Facture.objects.filter(societe=societe).exclude(statut_obr='ANNULE').select_related('client', 'cree_par').prefetch_related('lignes__produit', 'lignes__service').order_by('-date_facture')

    if f['date_debut']:
        qs = qs.filter(date_facture__gte=f['date_debut'])
    if f['date_fin']:
        qs = qs.filter(date_facture__lte=f['date_fin'])
    if f['produit_id']:
        qs = qs.filter(lignes__produit__id=f['produit_id']).distinct()
    if f['service_id']:
        qs = qs.filter(lignes__service__id=f['service_id']).distinct()
    qs = filtrer_par_mode(qs, f['mode'])

    lignes_rapport, tot = _lignes_rapport_facturation(qs)
    data = [_row_rapport_facturation(r) for r in lignes_rapport]
    data.append(_totaux_row_rapport_facturation(tot))

    try:
        chemin = generer_excel("Facturation", COLONNES_FACTURATION, data, "facturation")
    except Exception as e:
        messages.error(request, f"Échec export Excel : {e}")
        return redirect('rapports:facturation')
    return _reponse_fichier(chemin)


@login_required
def export_facturation_pdf(request):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('rapports:facturation')

    f = get_filtres(request)

    qs = Facture.objects.filter(societe=societe).exclude(statut_obr='ANNULE').select_related('client', 'cree_par').prefetch_related('lignes__produit', 'lignes__service').order_by('-date_facture')

    if f['date_debut']:
        qs = qs.filter(date_facture__gte=f['date_debut'])
    if f['date_fin']:
        qs = qs.filter(date_facture__lte=f['date_fin'])
    if f['produit_id']:
        qs = qs.filter(lignes__produit__id=f['produit_id']).distinct()
    if f['service_id']:
        qs = qs.filter(lignes__service__id=f['service_id']).distinct()
    qs = filtrer_par_mode(qs, f['mode'])

    lignes_rapport, tot = _lignes_rapport_facturation(qs)
    data = [_row_rapport_facturation(r) for r in lignes_rapport]
    data.append(_totaux_row_rapport_facturation(tot))

    # Important : on passe orientation="landscape"
    try:
        chemin = generer_pdf(
            titre="Rapport Facturation",
            colonnes=COLONNES_FACTURATION,
            lignes=data,
            type_rapport="facturation",
            orientation="landscape"      # ← Ici le changement
        )
    except Exception as e:
        messages.error(request, f"Échec export PDF : {e}")
        return redirect('rapports:facturation')
    return _reponse_fichier(chemin)



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

    qs = filtrer_par_mode(qs, f['mode'], facture_field='facture__')

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
    return _reponse_fichier(chemin)


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

    qs = filtrer_par_mode(qs, f['mode'], facture_field='facture__')

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
    return _reponse_fichier(chemin)
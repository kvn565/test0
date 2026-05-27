# facturer/views.py — VERSION CORRIGÉE & ALIGNÉE OBR (mars 2025)

import json
import logging
import os
from decimal import Decimal

import qrcode
import base64
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST, require_http_methods
from django.utils import timezone
from django.template.loader import render_to_string
from django.conf import settings

from weasyprint import HTML

from .models import Facture, LigneFacture
from .forms import FactureHeaderForm
from .obr_service import envoyer_facture_obr, annuler_facture_obr
from .services.calculators import get_taux_tva_effectif

from produits.models import Produit
from services.models import Service
from taux.models import TauxTVA
from stock.models import SortieStock, EntreeStock
from decimal import Decimal, ROUND_DOWN

from .forms import FactureHeaderForm, LigneFactureForm

logger = logging.getLogger(__name__)

def _fmt(d: Decimal | float | int | None, default="0.000") -> float:
    """Tronque strictement à 3 décimales et retourne float pour JSON."""
    if d is None:
        return 0.000
    try:
        dec = Decimal(str(d))
        return float(dec.quantize(Decimal('0.001'), rounding=ROUND_DOWN))
    except:
        return float(Decimal(default))


# ====================== HELPERS ======================
def _check_droit(request):
    if request.user.is_superuser:
        return None, "Superadmin n'a pas de société directe."

    societe = getattr(request.user, 'societe', None)
    if not societe:
        return None, "Aucune société associée à votre compte."

    has_right = (
        request.user.droit_facture_pnb or
        request.user.droit_facture_fdnb or
        request.user.droit_facture_particulier or
        request.user.type_poste == 'DIRECTEUR'
    )
    if not has_right:
        return None, "Vous n'avez pas les droits pour accéder à la facturation."

    return societe, None


def _get_societe_info(societe):
    return {
        'nom': societe.nom,
        'nif': societe.nif,
        'registre_commerce': getattr(societe, 'registre', ''),
        'telephone': getattr(societe, 'telephone', ''),
        'adresse_complete': getattr(societe, 'adresse_complete', ''),
        'commune': getattr(societe, 'commune', ''),
        'quartier': getattr(societe, 'quartier', ''),
        'avenue': getattr(societe, 'avenue', ''),
        'numero_rue': getattr(societe, 'numero', ''),
        'assujeti_tva': getattr(societe, 'assujeti_tva', False),
        'centre_fiscal': getattr(societe, 'centre_fiscale', ''),
    }


# ──────────────────────────────────────────────
#  LISTE FACTURES
# ──────────────────────────────────────────────

@login_required
def facture_liste(request):
    societe, err = _check_droit(request)
    if err:
        messages.error(request, err)
        return redirect('accueil')

    Facture.objects.filter(societe=societe, statut_obr='EN_ATTENTE', lignes__isnull=True).delete()

    qs = Facture.objects.filter(societe=societe).select_related('client').order_by('-date_facture', '-id')

    q = request.GET.get('q', '').strip()
    statut = request.GET.get('statut', '')
    type_f = request.GET.get('type', '')

    if q:
        qs = qs.filter(
            Q(numero__icontains=q) |
            Q(client__nom__icontains=q) |
            Q(bon_commande__icontains=q)
        )
    if statut:
        qs = qs.filter(statut_obr=statut)
    if type_f:
        qs = qs.filter(type_facture=type_f)

    base = Facture.objects.filter(societe=societe)
    stats = {
        'total': base.count(),
        'en_attente': base.filter(statut_obr='EN_ATTENTE').count(),
        'envoyes': base.filter(statut_obr='ENVOYE').count(),
        'echecs': base.filter(statut_obr='ECHEC').count(),
        'annulees': base.filter(statut_obr='ANNULE').count(),
    }

    paginator = Paginator(qs, 10)
    page_number = request.GET.get('page', 1)

    try:
        factures_page = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        factures_page = paginator.page(1)

    return render(request, 'facturer/liste.html', {
        'factures': factures_page,
        'page_obj': factures_page,
        'stats': stats,
        'header_form': FactureHeaderForm(societe=societe),
        'q': q,
        'statut': statut,
        'type_f': type_f,
        'types': Facture.TYPE_CHOICES,
        'statuts': Facture.STATUT_OBR_CHOICES,
        'produits_qs': Produit.objects.filter(societe=societe).order_by('designation'),
        'services_qs': Service.objects.filter(societe=societe).order_by('designation'),
    })


# ──────────────────────────────────────────────
#  DÉTAIL FACTURE
# ──────────────────────────────────────────────

@login_required
def facture_detail(request, pk):
    societe, err = _check_droit(request)
    if err:
        messages.error(request, err)
        return redirect('accueil')

    facture = Facture.objects.filter(pk=pk).select_related('client', 'facture_originale', 'societe').first()

    if not facture:
        messages.warning(request, "La session de facturation a été annulée ou la facture n'existe plus.")
        return redirect('facturer:liste')

    if not societe or facture.societe != societe:
        messages.error(request, "Vous n'avez pas accès à cette facture.")
        return redirect('facturer:liste')

    if facture.statut_obr == 'EN_ATTENTE':
        request.session['facture_en_cours'] = facture.pk
        request.session.modified = True

    lignes = facture.lignes.select_related('produit', 'service', 'taux_tva').all()

    if facture.type_facture == 'FA' and facture.facture_originale:
        produits = Produit.objects.filter(
            id__in=facture.facture_originale.lignes.values_list('produit_id', flat=True)
        ).order_by('designation')
    else:
        produits = Produit.objects.filter(societe=societe).order_by('designation')

    return render(request, 'facturer/detail.html', {
        'facture': facture,
        'lignes': lignes,
        'produits': produits,
        'services': Service.objects.filter(societe=societe).order_by('designation'),
    })


# ──────────────────────────────────────────────
#  SUPPRIMER FACTURE
# ──────────────────────────────────────────────

@login_required
@require_POST
def facture_supprimer(request, pk):
    societe, err = _check_droit(request)
    if err:
        messages.error(request, err)
        return redirect('accueil')

    facture = get_object_or_404(Facture, pk=pk, societe=societe)

    if facture.statut_obr not in ('EN_ATTENTE', 'ECHEC'):
        messages.error(request, "Impossible de supprimer une facture déjà envoyée ou annulée à l'OBR.")
        return redirect('facturer:detail', pk=pk)

    num = facture.display_numero

    with transaction.atomic():
        facture.nettoyer_mouvements_stock()
        facture.lignes.all().delete()
        facture.delete()

    messages.success(request, f"Facture {num} supprimée avec succès.")
    return redirect('facturer:liste')


@login_required
@require_POST
def facture_annuler(request, pk):
    societe, err = _check_droit(request)
    if err:
        return JsonResponse({'ok': False, 'error': err}, status=403)

    facture = get_object_or_404(Facture, pk=pk, societe=societe)
    statut = (facture.statut_obr or '').strip().upper()
    motif = request.POST.get('motif', '').strip()

    if statut == 'ENVOYE':
        if not motif:
            return JsonResponse({
                'ok': False,
                'error': "Le motif d'annulation est obligatoire pour une facture envoyée à l'OBR."
            })

        try:
            result = annuler_facture_obr(facture, motif=motif)

            if result.get('success'):
                with transaction.atomic():
                    facture.statut_obr = 'ANNULE'
                    facture.message_obr = result.get('message', 'Annulée avec succès')
                    facture.motif_avoir = motif
                    facture.date_annulation = timezone.now()
                    facture.save(update_fields=['statut_obr', 'message_obr', 'motif_avoir', 'date_annulation'])

                return JsonResponse({
                    'ok': True,
                    'message': result.get('message', 'Facture annulée avec succès auprès de l\'OBR.')
                })
            else:
                return JsonResponse({
                    'ok': False,
                    'error': result.get('message', 'Échec de l\'annulation auprès de l\'OBR.')
                })

        except Exception as e:
            logger.exception(f"Erreur annulation OBR - Facture {pk}")
            return JsonResponse({'ok': False, 'error': f"Erreur OBR : {str(e)}"}, status=500)

    elif statut in ('EN_ATTENTE', 'ECHEC'):
        try:
            if request.session.get('facture_en_cours') == pk:
                del request.session['facture_en_cours']
                request.session.modified = True

            num = facture.display_numero

            with transaction.atomic():
                facture.nettoyer_mouvements_stock()
                facture.lignes.all().delete()
                facture.delete()

            return JsonResponse({
                'ok': True,
                'message': f"Facture {num} supprimée définitivement."
            })

        except Exception as e:
            logger.exception(f"Erreur suppression facture {pk}")
            return JsonResponse({'ok': False, 'error': f"Erreur interne : {str(e)}"}, status=500)

    else:
        return JsonResponse({
            'ok': False,
            'error': f"Impossible d'annuler cette facture (statut : {facture.get_statut_obr_display()})"
        }, status=400)


# ──────────────────────────────────────────────
#  AJAX — CRÉER FACTURE
# ──────────────────────────────────────────────

@login_required
@require_POST
def ajax_creer_facture(request):
    societe, err = _check_droit(request)
    if err:
        return JsonResponse({'ok': False, 'error': err}, status=403)

    anciennes = Facture.objects.filter(societe=societe, statut_obr='EN_ATTENTE')
    for anc in anciennes:
        try:
            anc.nettoyer_mouvements_stock()
            anc.lignes.all().delete()
            anc.delete()
        except Exception as ex:
            logger.warning(f"Impossible de supprimer l'ancienne facture: {ex}")

    form = FactureHeaderForm(societe=societe, data=request.POST)

    if not form.is_valid():
        return JsonResponse({'ok': False, 'errors': form.errors.get_json_data()}, status=400)

    try:
        with transaction.atomic():
            facture = form.save(commit=False)
            facture.societe = societe
            facture.statut_obr = 'EN_ATTENTE'
            facture.cree_par = request.user
            facture.save()

            request.session['facture_en_cours'] = facture.pk
            request.session.modified = True

            return JsonResponse({
                'ok': True,
                'facture_id': facture.pk,
                'message': 'Facture créée en attente'
            })

    except Exception as e:
        logger.exception("Erreur création facture")
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


# ──────────────────────────────────────────────
#  AJAX — ENVOYER À OBR
# ──────────────────────────────────────────────

@login_required
@require_POST
def ajax_envoyer_obr(request, pk):
    societe, err = _check_droit(request)
    if err:
        return JsonResponse({'ok': False, 'error': err}, status=403)

    facture = get_object_or_404(Facture, pk=pk, societe=societe)

    if facture.statut_obr != 'EN_ATTENTE':
        return JsonResponse({'ok': False, 'error': f"Statut actuel : {facture.get_statut_obr_display()}"}, status=400)

    if facture.lignes.count() == 0:
        return JsonResponse({'ok': False, 'error': 'Facture vide'}, status=400)

    try:
        with transaction.atomic():
            facture.nettoyer_mouvements_stock()

            for ligne in facture.lignes.select_related('produit').all():
                if ligne.produit:
                    ligne.produit.ajuster_stock(
                        quantite=ligne.quantite,
                        type_facture=facture.type_facture,
                        facture=facture
                    )

        result = envoyer_facture_obr(facture)

        if result.get('success'):
            if request.session.get('facture_en_cours') == pk:
                del request.session['facture_en_cours']
                request.session.modified = True

            return JsonResponse({
                'ok': True,
                'message': 'Facture envoyée avec succès à l\'OBR et stock synchronisé.'
            })
        else:
            error_msg = result.get('message', 'Échec de l\'envoi à l\'OBR')
            return JsonResponse({'ok': False, 'error': error_msg}, status=400)

    except Exception as e:
        logger.exception(f"Erreur envoi OBR facture {pk}")
        return JsonResponse({'ok': False, 'error': f"Erreur : {str(e)}"}, status=500)


# ──────────────────────────────────────────────
#  AJAX — FACTURES CLIENT (pour FA)
# ──────────────────────────────────────────────

@login_required
@require_http_methods(["GET"])
def ajax_get_factures_client(request, client_id):
    societe, err = _check_droit(request)
    if err:
        return JsonResponse({'ok': False, 'error': err}, status=403)

    if not client_id:
        return JsonResponse({'ok': True, 'factures': []})

    factures = Facture.objects.filter(
        societe=societe,
        client_id=client_id,
        type_facture='FN'
    ).select_related('client').order_by('-date_facture', '-numero')

    data = [
        {
            'id': f.pk,
            'text': f"{f.display_numero} — {f.date_facture.strftime('%d/%m/%Y')} — {float(f.total_ttc or 0)} {f.devise}"
        }
        for f in factures
    ]

    return JsonResponse({'ok': True, 'factures': data})


# ──────────────────────────────────────────────
#  AJAX — PRODUITS FACTURE ORIGINALE (pour FA)
# ──────────────────────────────────────────────

@login_required
@require_http_methods(["GET"])
def ajax_get_produits_facture_originale(request, facture_id):
    societe, err = _check_droit(request)
    if err:
        return JsonResponse({'ok': False, 'error': err}, status=403)

    facture_originale = get_object_or_404(Facture, pk=facture_id, societe=societe, type_facture='FN')
    lignes = facture_originale.lignes.filter(produit__isnull=False).select_related('produit')

    data = [
        {
            'id': ligne.produit.pk,
            'designation': ligne.produit.designation,
            'quantite_vendue': float(ligne.quantite),
            'prix_ttc': float(ligne.prix_vente_tvac),
            'taux_tva': float(ligne.taux_tva),
        }
        for ligne in lignes
    ]

    return JsonResponse({'ok': True, 'produits': data})


# ──────────────────────────────────────────────
#  AJAX — TAUX TVA
# ──────────────────────────────────────────────

@require_http_methods(["GET"])
@login_required
def get_taux_tva(request, produit_id):
    try:
        societe, err = _check_droit(request)
        if err:
            return JsonResponse({'error': err}, status=403)

        produit = get_object_or_404(Produit, id=produit_id, societe=societe)
        facture_id = request.GET.get('facture_id')

        if not facture_id:
            return JsonResponse({'error': 'facture_id manquant'}, status=400)

        facture = get_object_or_404(Facture, id=facture_id, societe=societe)
        taux_obj = get_taux_tva_effectif(societe, produit, facture)

        return JsonResponse({
            'taux_tva_id': taux_obj.id if taux_obj else None,
            'taux_valeur': float(taux_obj.valeur) if taux_obj else 0.0,
            'taux_display': f"{float(taux_obj.valeur) if taux_obj else 0} %"
        })

    except Exception as e:
        logger.exception("Erreur get_taux_tva")
        return JsonResponse({'error': str(e)}, status=400)


# ──────────────────────────────────────────────
#  AJAX — INFOS PRODUIT / SERVICE
# ──────────────────────────────────────────────

@require_http_methods(["GET"])
@login_required
def ajax_info_produit(request, pk):
    societe, err = _check_droit(request)
    if err:
        return JsonResponse({'ok': False, 'error': err}, status=403)

    produit = get_object_or_404(Produit, pk=pk, societe=societe)

    facture_id = request.GET.get('facture_id')
    facture = Facture.objects.filter(pk=facture_id, societe=societe).first() if facture_id else None

    taux_obj = get_taux_tva_effectif(societe, produit)

    return JsonResponse({
        'ok': True,
        'designation': produit.designation or '—',
        'prix_ttc': _fmt(getattr(produit, 'prix_vente_tvac', 0)),
        'taux_tva': _fmt(taux_obj.valeur) if taux_obj and hasattr(taux_obj, 'valeur') else 0.000,
        'stock': _fmt(getattr(produit, 'stock_projete', getattr(produit, 'stock_disponible', 0))),
        'produit_id': produit.id,
    })


@require_http_methods(["GET"])
@login_required
def ajax_info_service(request, pk):
    societe, err = _check_droit(request)
    if err:
        return JsonResponse({'ok': False, 'error': err}, status=403)

    service = get_object_or_404(Service, pk=pk, societe=societe)
    facture_id = request.GET.get('facture_id')

    facture = None
    if facture_id:
        facture = Facture.objects.filter(pk=facture_id, societe=societe).first()

    taux_obj = get_taux_tva_effectif(societe, service, facture)
    prix_vente = Decimal(str(service.prix_vente or 0))

    return JsonResponse({
        'ok': True,
        'designation': service.designation or '—',
        'prix_ttc': _fmt(prix_vente),
        'taux_tva': _fmt(taux_obj.valeur) if taux_obj else 0.000,
        'taux_tva_id': taux_obj.id if taux_obj else None,
        'stock': '—',
    })


# ──────────────────────────────────────────────
#  AJAX — AJOUTER LIGNE
# ──────────────────────────────────────────────

@login_required
@require_POST
def ajax_ajouter_ligne(request):
    societe, err = _check_droit(request)
    if err:
        return JsonResponse({'ok': False, 'error': err}, status=403)

    try:
        payload = json.loads(request.body)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Données invalides'}, status=400)

    facture_id = payload.get('facture_id')
    facture = get_object_or_404(Facture, pk=facture_id, societe=societe)

    form = LigneFactureForm(
        data={
            'produit': payload.get('produit_id'),
            'service': payload.get('service_id'),
            'quantite': payload.get('quantite'),
            'prix_vente_tvac': payload.get('prix_tvac'),
        },
        societe=societe,
        facture=facture
    )

    if form.is_valid():
        try:
            with transaction.atomic():
                produit_obj = form.cleaned_data.get('produit')
                stock_avant = Decimal('0')

                if produit_obj:
                    stock_avant = produit_obj.stock_projete

                ligne = form.save()

                if produit_obj:
                    if facture.type_facture == 'FN':
                        stock_apres = max(stock_avant - ligne.quantite, Decimal('0'))
                    elif facture.type_facture == 'FA':
                        stock_apres = stock_avant + ligne.quantite
                    else:
                        stock_apres = stock_avant
                else:
                    stock_apres = None

                facture.recalculer_totaux()
                facture.refresh_from_db()

                return JsonResponse({
                    'ok': True,
                    'ligne_id': ligne.pk,
                    'designation': ligne.designation,
                    'prix_tvac': _fmt(ligne.prix_vente_tvac),
                    'quantite': _fmt(ligne.quantite),
                    'taux_tva': _fmt(ligne.taux_tva.valeur) if ligne.taux_tva else 0.000,
                    'montant_ht': _fmt(ligne.montant_ht),
                    'montant_tva': _fmt(ligne.montant_tva),
                    'montant_ttc': _fmt(ligne.montant_ttc),
                    'stock_apres': _fmt(stock_apres) if stock_apres is not None else None,
                    'produit_id': produit_obj.pk if produit_obj else None,
                    'total_ht': _fmt(facture.total_ht),
                    'total_tva': _fmt(facture.total_tva),
                    'total_ttc': _fmt(facture.total_ttc),
                    'message': "Ligne ajoutée"
                })

        except Exception as e:
            logger.exception("Erreur sauvegarde ligne")
            return JsonResponse({'ok': False, 'error': f"Erreur interne : {str(e)}"}, status=500)

    else:
        errors = [f"{field}: {', '.join(er_list)}" for field, er_list in form.errors.items()]
        return JsonResponse({'ok': False, 'error': " | ".join(errors)}, status=400)


# ──────────────────────────────────────────────
#  AJAX — MODIFIER LIGNE
# ──────────────────────────────────────────────

@login_required
@require_POST
def ajax_modifier_ligne(request):
    societe, err = _check_droit(request)
    if err:
        return JsonResponse({'ok': False, 'error': err}, status=403)

    try:
        payload = json.loads(request.body)
        ligne_id = payload.get('ligne_id')
        ligne = get_object_or_404(LigneFacture, pk=ligne_id, facture__societe=societe)
        facture = ligne.facture

        if facture.statut_obr != 'EN_ATTENTE':
            return JsonResponse({'ok': False, 'error': "Modification impossible sur une facture validée"}, status=400)

        ligne.nettoyer_mouvements_stock()

        form = LigneFactureForm(
            data={
                'produit': payload.get('produit_id'),
                'service': payload.get('service_id'),
                'quantite': payload.get('quantite'),
                'prix_vente_tvac': payload.get('prix_tvac'),
            },
            instance=ligne,
            societe=societe,
            facture=facture
        )

        if form.is_valid():
            with transaction.atomic():
                ligne = form.save()
                facture.recalculer_totaux()
                facture.refresh_from_db()

                return JsonResponse({
                    'ok': True,
                    'ligne_id': ligne.pk,
                    'designation': ligne.designation,
                    'prix_tvac': _fmt(ligne.prix_vente_tvac),
                    'quantite': _fmt(ligne.quantite),
                    'taux_tva': float(ligne.taux_tva.valeur) if ligne.taux_tva else 0,
                    'montant_ht': _fmt(ligne.montant_ht),
                    'montant_tva': _fmt(ligne.montant_tva),
                    'montant_ttc': _fmt(ligne.montant_ttc),
                    'total_ht': _fmt(facture.total_ht),
                    'total_tva': _fmt(facture.total_tva),
                    'total_ttc': _fmt(facture.total_ttc),
                    'stock_apres': _fmt(ligne.produit.stock_projete) if ligne.produit else None,
                    'produit_id': ligne.produit_id,
                    'message': "Ligne modifiée"
                })
        else:
            errors = [f"{field}: {', '.join(er_list)}" for field, er_list in form.errors.items()]
            return JsonResponse({'ok': False, 'error': " | ".join(errors)}, status=400)

    except Exception as e:
        logger.exception("Erreur modification ligne")
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


# ──────────────────────────────────────────────
#  AJAX — SUPPRIMER LIGNE
# ──────────────────────────────────────────────

@login_required
@require_POST
def ajax_supprimer_ligne(request):
    societe, err = _check_droit(request)
    if err:
        return JsonResponse({'ok': False, 'error': err}, status=403)

    ligne_id = request.POST.get('ligne_id') or request.POST.get('id')
    ligne = get_object_or_404(
        LigneFacture.objects.select_related('facture', 'produit'),
        pk=ligne_id,
        facture__societe=societe
    )

    facture = ligne.facture

    try:
        with transaction.atomic():
            ligne.delete()
            facture.recalculer_totaux()
            facture.refresh_from_db()

        return JsonResponse({
            'ok': True,
            'total_ht': _fmt(facture.total_ht),
            'total_tva': _fmt(facture.total_tva),
            'total_ttc': _fmt(facture.total_ttc),
        })

    except Exception as e:
        logger.exception(f"Erreur suppression ligne {ligne_id}")
        return JsonResponse({'ok': False, 'error': 'Erreur lors de la suppression'}, status=500)


# ──────────────────────────────────────────────
#  HELPER CONTEXTE FACTURE
# ──────────────────────────────────────────────

def _nombre_en_lettres_fr(n):
    """Convertit un entier en lettres françaises (jusqu'à 999 999 999 999)."""
    if n == 0:
        return 'zéro'

    units = ['', 'un', 'deux', 'trois', 'quatre', 'cinq', 'six', 'sept',
             'huit', 'neuf', 'dix', 'onze', 'douze', 'treize', 'quatorze',
             'quinze', 'seize', 'dix-sept', 'dix-huit', 'dix-neuf']
    tens  = ['', '', 'vingt', 'trente', 'quarante', 'cinquante',
             'soixante', 'soixante', 'quatre-vingt', 'quatre-vingt']

    def below_100(n):
        if n < 20:
            return units[n]
        t, u = divmod(n, 10)
        if t == 7:
            u += 10
            return 'soixante' + ('-et-' if u == 11 else '-') + units[u]
        if t == 9:
            u += 10
            return 'quatre-vingt' + ('-' + units[u] if u > 10 else ('s' if u == 0 else '-' + units[u]))
        if t == 8:
            return 'quatre-vingt' + ('' if u == 0 else '-' + units[u])
        return tens[t] + ('-et-' + units[u] if u == 1 else ('-' + units[u] if u else ''))

    def below_1000(n):
        if n < 100:
            return below_100(n)
        c, r = divmod(n, 100)
        if c == 1:
            return 'cent' + ('' if r == 0 else '-' + below_100(r))
        return units[c] + '-cent' + ('s' if r == 0 else '-' + below_100(r))

    result = ''
    milliards, n = divmod(n, 1_000_000_000)
    millions,  n = divmod(n, 1_000_000)
    milliers,  n = divmod(n, 1_000)

    if milliards:
        result += below_1000(milliards) + (' milliard ' if milliards == 1 else ' milliards ')
    if millions:
        result += below_1000(millions) + (' million ' if millions == 1 else ' millions ')
    if milliers:
        result += ('mille ' if milliers == 1 else below_1000(milliers) + '-mille ')
    if n:
        result += below_1000(n)

    return result.strip()


def _prepare_facture_context(facture, societe, for_pos=False):
    """
    Prépare le contexte pour les templates de facture.
    Montant en lettres toujours recalculé depuis total_ttc (3 décimales, sans arrondi).
    """
    import qrcode
    import base64
    from io import BytesIO
    from pathlib import Path
    from urllib.request import pathname2url
    from django.conf import settings
    from decimal import Decimal, ROUND_DOWN

    # ====================== LOGO ======================
    logo_path = None
    if societe.facture_logo and societe.facture_logo.name:
        abs_path = Path(settings.MEDIA_ROOT) / societe.facture_logo.name
        if abs_path.is_file():
            logo_path = "file:///" + pathname2url(str(abs_path)).lstrip("/")

    # ====================== MONTANT EN LETTRES ======================
    # Recalcul TOUJOURS depuis total_ttc — pas de champ modèle
    montant_lettres = ''

    try:
        raw = str(facture.total_ttc).strip().replace(' ', '').replace(',', '.')
        total = Decimal(raw).quantize(Decimal('0.001'), rounding=ROUND_DOWN)

        total_str = str(total)
        if '.' in total_str:
            entiere_str, decimale_str = total_str.split('.')
            decimale_str = decimale_str.ljust(3, '0')[:3]
        else:
            entiere_str, decimale_str = total_str, '000'

        partie_entiere = int(entiere_str)
        decimal_part   = int(decimale_str)

        devise = "francs burundais" if facture.devise.upper() == "BIF" else facture.devise.lower()
        lettres_entiere = _nombre_en_lettres_fr(partie_entiere).capitalize()

        if decimal_part == 0:
            montant_lettres = f"{lettres_entiere} {devise}."
        else:
            lettres_decimale = _nombre_en_lettres_fr(decimal_part)
            montant_lettres = f"{lettres_entiere} {devise} et {lettres_decimale} millièmes."

    except Exception as e:
        logger.warning(f"Erreur montant_lettres facture {facture.pk}: {type(e).__name__}: {e}")
        try:
            raw = str(facture.total_ttc).strip().replace(',', '.')
            total_formate = Decimal(raw).quantize(Decimal('0.001'), rounding=ROUND_DOWN)
        except Exception:
            total_formate = facture.total_ttc
        montant_lettres = f"{total_formate} {facture.devise}"

    # ====================== QR CODE ======================
    qr_code_url = None
    identifiant = facture.invoice_identifier or facture.numero
    if identifiant:
        try:
            qr = qrcode.QRCode(version=1, box_size=10, border=4)
            qr.add_data(identifiant)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            qr_code_url = "data:image/png;base64," + base64.b64encode(buffered.getvalue()).decode('utf-8')
        except Exception as e:
            logger.error(f"Erreur QR Code: {e}")

    # ====================== PIED DE PAGE ======================
    pied_page = (getattr(societe, 'facture_pied_page', '') or '').strip()

    return {
        'facture':            facture,
        'lignes':             facture.lignes.select_related('produit', 'service', 'taux_tva').all(),
        'societe':            societe,
        'logo_path':          logo_path,
        'montant_lettres':    montant_lettres,
        'qr_code_url':        qr_code_url,
        'invoice_identifier': identifiant,
        'pied_page':          pied_page,
        'now':                timezone.now(),
    }
# ──────────────────────────────────────────────
#  PDF A4
# ──────────────────────────────────────────────

@login_required
def facture_generer_pdf(request, pk):
    """Génère et sauvegarde media/factures/facturer.pdf"""
    societe, err = _check_droit(request)
    if err:
        messages.error(request, err)
        return redirect('accueil')

    facture = get_object_or_404(
        Facture.objects.select_related('client', 'societe', 'facture_originale'),
        pk=pk,
        societe=societe
    )

    context = _prepare_facture_context(facture, societe, for_pos=False)
    html_string = render_to_string('facturer/print_a4.html', context)

    try:
        weasy_html = HTML(string=html_string, base_url=request.build_absolute_uri('/'))

        pdf_dir = os.path.join(settings.MEDIA_ROOT, "factures")
        os.makedirs(pdf_dir, exist_ok=True)
        pdf_path = os.path.join(pdf_dir, "facturer.pdf")

        weasy_html.write_pdf(target=pdf_path)

        with open(pdf_path, "rb") as f:
            pdf_data = f.read()

        response = HttpResponse(pdf_data, content_type='application/pdf')
        response['Content-Disposition'] = 'inline; filename="facturer.pdf"'

        logger.info(f"PDF A4 sauvegardé : {pdf_path}")
        return response

    except Exception as e:
        logger.exception(f"Erreur PDF A4 facture {pk}")
        messages.error(request, "Erreur lors de la génération du PDF.")
        return redirect('facturer:detail', pk=pk)


# ──────────────────────────────────────────────
#  PDF POS / TICKET
# ──────────────────────────────────────────────

@login_required
def facture_generer_pos_pdf(request, pk):
    """Génère et sauvegarde media/pos_tickets/ticket.pdf"""
    societe, err = _check_droit(request)
    if err:
        messages.error(request, err)
        return redirect('accueil')

    facture = get_object_or_404(
        Facture.objects.select_related('client', 'societe'),
        pk=pk,
        societe=societe
    )

    context = _prepare_facture_context(facture, societe, for_pos=True)
    html_string = render_to_string('facturer/print_pos.html', context)

    try:
        weasy_html = HTML(string=html_string, base_url=request.build_absolute_uri('/'))

        pdf_dir = os.path.join(settings.MEDIA_ROOT, "pos_tickets")
        os.makedirs(pdf_dir, exist_ok=True)
        pdf_path = os.path.join(pdf_dir, "ticket.pdf")

        weasy_html.write_pdf(target=pdf_path)

        with open(pdf_path, "rb") as f:
            pdf_data = f.read()

        response = HttpResponse(pdf_data, content_type='application/pdf')
        response['Content-Disposition'] = 'inline; filename="ticket.pdf"'

        logger.info(f"PDF Ticket POS sauvegardé : {pdf_path}")
        return response

    except Exception as e:
        logger.exception(f"Erreur PDF POS facture {pk}")
        messages.error(request, "Erreur lors de la génération du ticket POS.")
        return redirect('facturer:detail', pk=pk)


# ──────────────────────────────────────────────
#  Redirections anciennes vues
# ──────────────────────────────────────────────

@login_required
def facture_imprimer_a4(request, pk):
    return redirect('facturer:generer_pdf', pk=pk)


@login_required
def facture_imprimer_pos(request, pk):
    return redirect('facturer:generer_pos_pdf', pk=pk)


# ──────────────────────────────────────────────
#  ANTI-ABANDON
# ──────────────────────────────────────────────

from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
@login_required
def ajax_supprimer_facture_en_attente(request):
    """
    Supprime la facture EN_ATTENTE si abandonnée (via sendBeacon).
    """
    pk = request.POST.get('facture_id') or request.session.get('facture_en_cours')

    if not pk:
        return JsonResponse({'ok': False, 'error': 'ID manquant'}, status=400)

    try:
        facture = Facture.objects.get(pk=pk, statut_obr='EN_ATTENTE')
        societe_user = getattr(request.user, 'societe', None)

        if societe_user and facture.societe == societe_user:
            with transaction.atomic():
                facture.nettoyer_mouvements_stock()
                facture.lignes.all().delete()
                facture.delete()

                if request.session.get('facture_en_cours') == int(pk):
                    del request.session['facture_en_cours']
                    request.session.modified = True

            return JsonResponse({'ok': True})

        return JsonResponse({'ok': False, 'error': 'Non autorisé'}, status=403)

    except Facture.DoesNotExist:
        return JsonResponse({'ok': True, 'info': 'Déjà traitée'})
    except Exception as e:
        logger.warning(f"Échec suppression abandon [PK={pk}]: {e}")
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)

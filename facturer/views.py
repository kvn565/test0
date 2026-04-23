# facturer/views.py — VERSION CORRIGÉE & ALIGNÉE OBR (mars 2025)

import json
import traceback
from decimal import Decimal
import qrcode
import base64
from io import BytesIO
import logging
import os

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

GTK_BIN_PATH = r"C:\Program Files\GTK3-Runtime Win64\bin"   # ← CHANGEZ CE CHEMIN selon votre installation

if os.path.exists(GTK_BIN_PATH):
    os.add_dll_directory(GTK_BIN_PATH)
else:
    print(f"ATTENTION : Chemin GTK non trouvé : {GTK_BIN_PATH}")

# WeasyPrint pour génération PDF
from weasyprint import HTML

from .models import Facture, LigneFacture
from .forms import FactureHeaderForm
from .obr_service import envoyer_facture_obr, annuler_facture_obr
from produits.models import Produit
from services.models import Service
from stock.models import SortieStock, EntreeStock

logger = logging.getLogger(__name__)
# ──────────────────────────────────────────────
#  HELPERS
# ──────────────────────────────────────────────

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
#  LISTE FACTURES — pagination 10 par page (plus pratique)
# ──────────────────────────────────────────────

@login_required
def facture_liste(request):
    societe, err = _check_droit(request)
    if err:
        messages.error(request, err)
        return redirect('accueil')

    qs = Facture.objects.filter(societe=societe).select_related('client').order_by('-date_facture', '-id')

    q      = request.GET.get('q', '').strip()
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
        'total':      base.count(),
        'en_attente': base.filter(statut_obr='EN_ATTENTE').count(),
        'envoyes':    base.filter(statut_obr='ENVOYE').count(),
        'echecs':     base.filter(statut_obr='ECHEC').count(),
        'annulees':   base.filter(statut_obr='ANNULE').count(),
    }

    paginator = Paginator(qs, 10)  # ← 10 au lieu de 5, plus confortable
    page_number = request.GET.get('page', 1)

    try:
        factures_page = paginator.page(page_number)
    except PageNotAnInteger:
        factures_page = paginator.page(1)
    except EmptyPage:
        factures_page = paginator.page(paginator.num_pages)

    return render(request, 'facturer/liste.html', {
        'factures':    factures_page,
        'page_obj':    factures_page,
        'stats':       stats,
        'header_form': FactureHeaderForm(societe=societe),
        'q':           q,
        'statut':      statut,
        'type_f':      type_f,
        'types':       Facture.TYPE_CHOICES,
        'statuts':     Facture.STATUT_OBR_CHOICES,
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

    # Correction importante : on cherche la facture sans forcer la société au début
    facture = get_object_or_404(
        Facture.objects.select_related('client', 'facture_originale'),
        pk=pk
    )

    # Sécurité : vérifier que l'utilisateur a accès à cette facture
    if facture.societe != societe and not request.user.is_superuser:
        messages.error(request, "Vous n'avez pas accès à cette facture.")
        return redirect('facturer:liste')

    # Si la facture est EN_ATTENTE, on active le blocage global
    if facture.statut_obr == 'EN_ATTENTE':
        request.session['facture_en_cours'] = facture.pk
        request.session.modified = True

    lignes = facture.lignes.select_related('produit', 'service').all()

    # Produits pour facture d'avoir
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
#  SUPPRIMER FACTURE (seulement si EN_ATTENTE ou ECHEC)
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
        facture.lignes.all().delete()
        facture.delete()

    messages.success(request, f"Facture {num} supprimée avec succès.")
    return redirect('facturer:liste')




@login_required
@require_POST
def facture_annuler(request, pk):
    societe, err = _check_droit(request)
    if err:
        messages.error(request, err)
        return redirect('facturer:liste')

    facture = get_object_or_404(Facture, pk=pk, societe=societe)
    statut = (facture.statut_obr or '').strip().upper()

    if statut == 'ANNULE':
        messages.warning(request, "Cette facture est déjà annulée auprès de l'OBR.")
        return redirect('facturer:detail', pk=pk)

    motif = request.POST.get('motif', '').strip()

    try:
        if statut == 'ENVOYE':
            if not motif:
                messages.error(request, "Le motif d'annulation est obligatoire pour une facture envoyée à l'OBR.")
                return redirect('facturer:detail', pk=pk)

            # Appel API HORS transaction (très important pour éviter le lock)
            result = annuler_facture_obr(facture, motif=motif)

            if result.get('success'):
                # On utilise le VRAI message renvoyé par l'OBR
                msg_obr = result.get('message', f"Facture {facture.display_numero} annulée avec succès auprès de l'OBR.")

                # Mise à jour propre dans une transaction courte
                with transaction.atomic():
                    facture.statut_obr = 'ANNULE'
                    facture.message_obr = msg_obr
                    facture.motif_avoir = motif
                    facture.date_annulation = timezone.now()
                    facture.save(update_fields=[
                        'statut_obr',
                        'message_obr',
                        'motif_avoir',
                        'date_annulation'
                    ])

                messages.success(request, msg_obr)   # ← Message clair de l'OBR
                logger.info(f"Annulation OBR réussie - Facture {facture.pk} - {msg_obr}")

            else:
                error_msg = result.get('message', "Échec de l'annulation auprès de l'OBR.")
                messages.error(request, error_msg)
                logger.warning(f"Échec annulation OBR - Facture {facture.pk} : {error_msg}")
                return redirect('facturer:detail', pk=pk)

        elif statut in ('EN_ATTENTE', 'ECHEC'):
            # Suppression locale sans appel OBR
            if request.session.get('facture_en_cours') == pk:
                del request.session['facture_en_cours']
                request.session.modified = True

            num = facture.display_numero

            with transaction.atomic():
                facture.lignes.all().delete()
                facture.delete()

            messages.success(request, f"Facture {num} supprimée définitivement (non envoyée à l'OBR).")

        else:
            messages.error(request, f"Statut non gérable pour annulation : {facture.get_statut_obr_display()}")
            return redirect('facturer:detail', pk=pk)

    except Exception as e:
        logger.exception(f"Erreur lors de l'annulation de la facture {pk}")
        messages.error(request, f"Erreur interne lors de l'annulation : {str(e)}")

    return redirect('facturer:liste')

# ──────────────────────────────────────────────
#  AJAX — ENVOYER À OBR (corrigé + logs améliorés)
# ──────────────────────────────────────────────

@login_required
@require_POST
def ajax_creer_facture(request):
    societe, err = _check_droit(request)
    if err:
        return JsonResponse({'ok': False, 'error': err}, status=403)

    if Facture.objects.filter(societe=societe, statut_obr='EN_ATTENTE').exists():
        return JsonResponse({
            'ok': False,
            'error': "Une facture est déjà en attente. Vous devez l'envoyer ou l'annuler avant d'en créer une nouvelle."
        }, status=400)

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

            # Activation du blocage global
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
#  ENVOI À L'OBR
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
        result = envoyer_facture_obr(facture)

        if result.get('success'):
            # Nettoyage du blocage après envoi réussi
            if request.session.get('facture_en_cours') == pk:
                del request.session['facture_en_cours']
                request.session.modified = True

            return JsonResponse({
                'ok': True,
                'message': 'Facture envoyée avec succès à l\'OBR',
            })
        else:
            return JsonResponse({'ok': False, 'error': result.get('message', 'Échec de l\'envoi')}, status=400)

    except Exception as e:
        logger.exception(f"Exception envoi OBR facture {pk}")
        return JsonResponse({'ok': False, 'error': 'Erreur interne serveur'}, status=500)

# ──────────────────────────────────────────────
#  AJAX — RÉCUPÉRER LES FACTURES FN D'UN CLIENT (pour création FA)
# ──────────────────────────────────────────────

@login_required
@require_http_methods(["GET"])
def ajax_get_factures_client(request, client_id):
    """Retourne uniquement les factures normales (FN) d'un client pour créer une facture d'avoir"""
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
#  AJAX — RÉCUPÉRER PRODUITS D'UNE FACTURE ORIGINALE (pour FA)
# ──────────────────────────────────────────────

@login_required
@require_http_methods(["GET"])
def ajax_get_produits_facture_originale(request, facture_id):
    """Retourne les produits présents dans une facture normale (FN) pour créer un avoir"""
    societe, err = _check_droit(request)
    if err:
        return JsonResponse({'ok': False, 'error': err}, status=403)

    facture_originale = get_object_or_404(Facture, pk=facture_id, societe=societe, type_facture='FN')

    # Récupère les produits uniques de la facture originale avec leur quantité vendue
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
#  AJAX — INFOS PRODUIT / SERVICE
# ──────────────────────────────────────────────

@require_http_methods(["GET"])
@login_required
def ajax_info_produit(request, pk):
    societe, err = _check_droit(request)
    if err:
        return JsonResponse({'ok': False, 'error': err}, status=403)

    produit = get_object_or_404(Produit, pk=pk, societe=societe)

    taux_tva = int(produit.taux_tva_valeur) if hasattr(produit, 'taux_tva_valeur') else 18

    data = {
        'ok': True,
        'designation': produit.designation or '—',
        'prix_ttc': float(produit.prix_vente_tvac or 0),
        'taux_tva': taux_tva,
        'stock': float(produit.stock_disponible),
    }

    # Ajout minimal pour facture d'avoir
    if request.GET.get('facture_originale'):
        try:
            fo = Facture.objects.get(pk=request.GET.get('facture_originale'), type_facture='FN')
            ligne = fo.lignes.filter(produit_id=pk).first()
            if ligne:
                data['quantite_max'] = float(ligne.quantite)
        except:
            pass

    return JsonResponse(data)


@require_http_methods(["GET"])
@login_required
def ajax_info_service(request, pk):
    societe, err = _check_droit(request)
    if err:
        return JsonResponse({'ok': False, 'error': err}, status=403)

    service = get_object_or_404(Service, pk=pk, societe=societe)

    taux_tva = int(service.taux_tva.valeur) if service.taux_tva and service.taux_tva.valeur is not None else 18

    return JsonResponse({
        'ok': True,
        'designation': service.designation or '—',
        'prix_ttc': float(service.prix or 0),
        'taux_tva': taux_tva,
        'stock': '—',
    })


# ──────────────────────────────────────────────
#  AJAX AJOUTER LIGNE — PAS de modif stock ici
# ──────────────────────────────────────────────


# ──────────────────────────────────────────────
#  AJAX — AJOUTER LIGNE (AVEC GESTION STOCK CONDITIONNELLE)
# ──────────────────────────────────────────────
@login_required
@require_POST
def ajax_ajouter_ligne(request):
    societe, err = _check_droit(request)
    if err:
        return JsonResponse({'ok': False, 'error': err}, status=403)

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({'ok': False, 'error': 'JSON invalide'}, status=400)

    facture_id = payload.get('facture_id')
    if not facture_id:
        return JsonResponse({'ok': False, 'error': 'facture_id manquant'}, status=400)

    facture = get_object_or_404(Facture, pk=facture_id, societe=societe)

    try:
        quantite = Decimal(str(payload.get('quantite') or '0')).quantize(Decimal('0.01'))
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Quantité invalide'}, status=400)

    if quantite <= 0:
        return JsonResponse({'ok': False, 'error': 'La quantité doit être supérieure à 0'}, status=400)

    produit_id = payload.get('produit_id')
    service_id = payload.get('service_id')

    if not (produit_id or service_id):
        return JsonResponse({'ok': False, 'error': 'Produit ou service requis'}, status=400)

    try:
        with transaction.atomic():
            produit = None
            service = None
            stock_avant = Decimal('0')
            stock_apres = Decimal('0')

            if produit_id:
                produit = get_object_or_404(
                    Produit.objects.select_for_update(),
                    pk=produit_id,
                    societe=societe
                )

                stock_avant = produit.stock_disponible

                # ====================== VALIDATION SPÉCIFIQUE POUR FACTURE D'AVOIR ======================
                if facture.type_facture == 'FA' and facture.facture_originale:
                    ligne_originale = facture.facture_originale.lignes.filter(
                        produit_id=produit_id
                    ).first()

                    if ligne_originale and quantite > ligne_originale.quantite:
                        return JsonResponse({
                            'ok': False,
                            'error': f'La quantité ne peut pas dépasser {float(ligne_originale.quantite)} '
                                     f'(quantité vendue sur la facture originale {facture.facture_originale.display_numero}).'
                        }, status=400)
                # =======================================================================================

                # Vérification doublon dans la facture en cours
                if facture.lignes.filter(produit_id=produit_id).exists():
                    return JsonResponse({
                        'ok': False,
                        'error': 'Ce produit est déjà présent dans cette facture.'
                    }, status=400)

                if facture.type_facture in ['FN', 'FA']:
                    produit.ajuster_stock(quantite=quantite, type_facture=facture.type_facture, facture=facture)

                designation = produit.designation
                prix_ttc = Decimal(str(produit.prix_vente_tvac or 0))
                taux_tva = Decimal(str(produit.taux_tva_valeur or 18))

            else:
                service = get_object_or_404(Service, pk=service_id, societe=societe)
                designation = service.designation
                prix_ttc = Decimal(str(service.prix or 0))
                taux_tva = Decimal(str(service.taux_tva.valeur if getattr(service.taux_tva, 'valeur', None) else 18))

            # Création de la ligne
            ligne = LigneFacture.objects.create(
                facture=facture,
                designation=designation,
                prix_vente_tvac=prix_ttc,
                quantite=quantite,
                taux_tva=taux_tva,
                produit=produit,
                service=service,
            )

            # Recalcul des totaux
            facture.recalculer_totaux()
            facture = Facture.objects.get(pk=facture.pk)   # Rechargement complet

            # Calcul du stock pour la réponse
            if produit:
                produit.refresh_from_db()
                stock_avant = produit.stock_disponible

                if facture.type_facture == 'FN':
                    stock_apres = stock_avant - quantite
                elif facture.type_facture == 'FA':
                    stock_apres = stock_avant + quantite
                else:
                    stock_apres = stock_avant

    except ValueError as ve:
        return JsonResponse({'ok': False, 'error': str(ve)}, status=400)
    except Exception as e:
        logger.exception(f"Erreur ajout ligne facture {facture_id}")
        return JsonResponse({'ok': False, 'error': 'Erreur serveur lors de l\'ajout'}, status=500)

    return JsonResponse({
        'ok': True,
        'ligne_id': ligne.pk,
        'designation': designation,
        'quantite': float(quantite),
        'prix_ttc': float(prix_ttc),
        'taux_tva': int(taux_tva),
        'total_ht': float(facture.total_ht or 0),
        'total_tva': float(facture.total_tva or 0),
        'total_ttc': float(facture.total_ttc or 0),
        'stock_avant': float(stock_avant),
        'stock_apres': float(stock_apres),
        'produit_id': produit.pk if produit else None,
    })
# ──────────────────────────────────────────────
#  AJAX SUPPRIMER LIGNE — RESTAURER STOCK SI FN
# ──────────────────────────────────────────────

@login_required
@require_POST
def ajax_supprimer_ligne(request):
    societe, err = _check_droit(request)
    if err:
        return JsonResponse({'ok': False, 'error': err}, status=403)

    try:
        data = json.loads(request.body)
        ligne_id = data.get('ligne_id')
    except Exception:
        return JsonResponse({'ok': False, 'error': 'JSON invalide'}, status=400)

    ligne = get_object_or_404(LigneFacture, pk=ligne_id, facture__societe=societe)
    facture = ligne.facture
    produit = ligne.produit

    try:
        with transaction.atomic():
            if produit and facture.type_facture in ['FN', 'FA']:
                # Inverse de l'ajout :
                # Si on supprime une FN → on doit remettre la quantité (comme FA)
                # Si on supprime une FA → on doit enlever la quantité (comme FN)
                inverse_type = 'FA' if facture.type_facture == 'FN' else 'FN'
                produit.ajuster_stock(
                    quantite=ligne.quantite,
                    type_facture=inverse_type,
                    facture=facture
                )

            ligne.delete()
            facture.recalculer_totaux()

    except Exception as e:
        logger.exception(f"Erreur suppression ligne {ligne_id}")
        return JsonResponse({'ok': False, 'error': 'Erreur lors de la suppression'}, status=500)

    return JsonResponse({
        'ok': True,
        'total_ht': float(facture.total_ht),
        'total_tva': float(facture.total_tva),
        'total_ttc': float(facture.total_ttc),
    })


# ──────────────────────────────────────────────
#  HELPERS (ajout recommandé)
# ──────────────────────────────────────────────
def _prepare_facture_context(facture, societe, for_pos=False):
    """Prépare le context commun pour A4 et POS - QR Code maintenant disponible pour les deux"""
    # Mise à jour des identifiants si nécessaire
    updated = False
    if not facture.numero:
        facture.generate_numero()
        updated = True
    if not facture.invoice_identifier:
        try:
            facture.generate_invoice_identifier()
            updated = True
        except Exception as e:
            logger.error(f"Erreur génération invoice_identifier pour facture {facture.pk}: {e}")

    if updated:
        facture.save(update_fields=['numero', 'invoice_identifier'])
        facture.refresh_from_db()

    # Montant en lettres
    montant_lettres = ''
    try:
        from num2words import num2words
        montant_lettres = num2words(
            int(round(facture.total_ttc or 0)), 
            lang='fr'
        ).capitalize() + " francs burundais."
    except Exception:
        montant_lettres = f"{facture.total_ttc or 0} francs burundais."

    # Génération QR Code (pour A4 ET POS maintenant)
    qr_code_url = None
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(facture.invoice_identifier)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
        qr_code_url = f"data:image/png;base64,{img_str}"
    except Exception as e:
        logger.error(f"Erreur QR Code facture {facture.pk}: {e}")

    return {
        'facture': facture,
        'lignes': facture.lignes.select_related('produit', 'service').all(),
        'societe': societe,
        'montant_lettres': montant_lettres,
        'qr_code_url': qr_code_url,          # Disponible pour POS aussi
        'invoice_identifier': facture.invoice_identifier,
        'now': timezone.now(),
    }


# ──────────────────────────────────────────────
#  PDF A4 — facture.pdf 
# ──────────────────────────────────────────────

@login_required
def facture_generer_pdf(request, pk):
    """Génère et sauvegarde media/factures/facturer.pdf + ouvre dans le navigateur"""
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
#  PDF POS / TICKET — ticket.pdf 
# ──────────────────────────────────────────────

@login_required
def facture_generer_pos_pdf(request, pk):
    """Génère et sauvegarde media/pos_tickets/ticket.pdf + ouvre dans le navigateur"""
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
#  Anciennes vues (redirigent vers les nouvelles) - conservées
# ──────────────────────────────────────────────

@login_required
def facture_imprimer_a4(request, pk):
    """Redirige vers la nouvelle génération PDF A4"""
    return redirect('facturer:generer_pdf', pk=pk)


@login_required
def facture_imprimer_pos(request, pk):
    """Redirige vers la nouvelle génération PDF POS"""
    return redirect('facturer:generer_pos_pdf', pk=pk)
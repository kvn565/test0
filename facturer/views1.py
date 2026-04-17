# facturer/views.py
import json
import traceback
from decimal import Decimal, ROUND_HALF_UP

import qrcode
import base64
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST, require_http_methods
from django.utils import timezone

from .models import Facture, LigneFacture
from .forms import FactureHeaderForm
from .obr_service import envoyer_facture_obr, annuler_facture_obr

from produits.models import Produit
from services.models import Service
from stock.models import SortieStock, EntreeStock


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
        getattr(request.user, 'droit_facture_pnb', False) or
        getattr(request.user, 'droit_facture_fdnb', False) or
        getattr(request.user, 'droit_facture_particulier', False) or
        request.user.type_poste == 'DIRECTEUR'
    )
    if not has_right:
        return None, "Vous n'avez pas les droits pour accéder à la facturation."

    return societe, None


def _get_societe_info(societe):
    return {
        'nom': societe.nom,
        'nif': societe.nif,
        'registre_commerce': getattr(societe, 'registre_commerce', ''),
        'telephone': getattr(societe, 'telephone', ''),
        'adresse_complete': getattr(societe, 'adresse_complete', ''),
        'commune': getattr(societe, 'commune', ''),
        'quartier': getattr(societe, 'quartier', ''),
        'avenue': getattr(societe, 'avenue', ''),
        'numero_rue': getattr(societe, 'numero', ''),
        'assujeti_tva': getattr(societe, 'assujeti_tva', False),
        'centre_fiscal': getattr(societe, 'centre_fiscal', ''),
        'tc': getattr(societe, 'tc', ''),
    }


# ──────────────────────────────────────────────
#  LISTE FACTURES — pagination 5 par page
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

    paginator = Paginator(qs, 5)
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

    facture = get_object_or_404(Facture.objects.select_related('client'), pk=pk, societe=societe)
    lignes  = facture.lignes.select_related('produit', 'service').all()

    return render(request, 'facturer/detail.html', {
        'facture':  facture,
        'lignes':   lignes,
        'produits': Produit.objects.filter(societe=societe).order_by('designation'),
        'services': Service.objects.filter(societe=societe).order_by('designation'),
    })


# ──────────────────────────────────────────────
#  SUPPRIMER FACTURE (seulement si EN_ATTENTE ou ECHEC)
# ──────────────────────────────────────────────

@login_required
@require_POST
def facture_supprimer(request, pk):
    # Vérifie les droits sur la société
    societe, err = _check_droit(request)
    if err:
        messages.error(request, err)
        return redirect('accueil')

    # Récupère la facture
    facture = get_object_or_404(Facture, pk=pk, societe=societe)

    # Vérifie que la facture peut être supprimée
    if facture.statut_obr not in ('EN_ATTENTE', 'ECHEC'):
        messages.error(request, "Impossible de supprimer une facture déjà envoyée ou annulée à l'OBR.")
        return redirect('facturer:detail', pk=pk)

    num = facture.display_numero

    with transaction.atomic():
        # Supprime les éventuelles lignes
        facture.lignes.all().delete()

        # Supprime la facture
        facture.delete()

    messages.success(request, f"Facture {num} supprimée avec succès.")
    return redirect('facturer:liste')

# ──────────────────────────────────────────────
#  ANNULER FACTURE (conforme OBR + gestion stock)
# ──────────────────────────────────────────────

@login_required
@require_POST
def facture_annuler(request, pk):
    societe, err = _check_droit(request)
    if err:
        return JsonResponse({'ok': False, 'error': err}, status=403)

    facture = get_object_or_404(Facture, pk=pk, societe=societe)

    if facture.statut_obr == 'ANNULE':
        return JsonResponse({'ok': False, 'error': 'Facture déjà annulée'}, status=400)

    if facture.statut_obr not in ('ENVOYE', 'ECHEC'):
        return JsonResponse({'ok': False, 'error': 'Annulation impossible dans cet état'}, status=400)

    motif = request.POST.get('motif', '').strip()
    if not motif:
        return JsonResponse({'ok': False, 'error': 'Motif obligatoire'}, status=400)

    try:
        with transaction.atomic():
            result = annuler_facture_obr(facture, motif=motif)

            if not result['success']:
                return JsonResponse({'ok': False, 'error': result['message']}, status=400)

            # Restauration stock si annulation réussie
            if facture.type_facture == 'FN':
                for ligne in facture.lignes.all():
                    if ligne.produit:
                        ligne.produit.quantite_stock = (ligne.produit.quantite_stock or 0) + ligne.quantite
                        ligne.produit.save(update_fields=['quantite_stock'])

            facture.statut_obr = 'ANNULE'
            facture.motif_avoir = f"Annulation : {motif}"
            facture.save(update_fields=['statut_obr', 'motif_avoir', 'message_obr'])

        return JsonResponse({'ok': True, 'message': 'Facture annulée et stock restauré'})

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'ok': False, 'error': 'Erreur serveur'}, status=500)


# ──────────────────────────────────────────────
#  AJAX — ENVOYER À OBR (modif stock ici)
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

        if result['success']:
            return JsonResponse({
                'ok': True,
                'message': result.get('message', 'Envoyée avec succès à l\'OBR – stock mis à jour'),
            })
        else:
            return JsonResponse({
                'ok': False,
                'error': result.get('message', 'Échec envoi OBR')
            }, status=400)

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'ok': False, 'error': 'Erreur serveur'}, status=500)


# ──────────────────────────────────────────────
#  AJAX — CRÉER FACTURE
# ──────────────────────────────────────────────

@login_required
@require_POST
def ajax_creer_facture(request):
    societe, err = _check_droit(request)
    if err:
        return JsonResponse({'ok': False, 'error': err}, status=403)

    form = FactureHeaderForm(societe=societe, data=request.POST)

    if not form.is_valid():
        return JsonResponse({'ok': False, 'errors': form.errors.get_json_data()}, status=400)

    try:
        with transaction.atomic():
            facture = form.save(commit=False)
            facture.societe = societe
            facture.cree_par = request.user

            # ✅ NE PAS générer le numéro ici
            # 👉 le modèle (save + generate_numero) s'en charge

            facture.save()

        return JsonResponse({
            'ok': True,
            'message': 'Facture créée',
            'facture_id': facture.pk,
            'numero': facture.numero,
        }, status=201)

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'ok': False, 'error': 'Erreur interne'}, status=500)

# ──────────────────────────────────────────────
#  AJAX — INFOS PRODUIT / SERVICE
# ──────────────────────────────────────────────

# Dans ajax_info_produit
@require_http_methods(["GET"])
@login_required
def ajax_info_produit(request, pk):
    societe, err = _check_droit(request)
    if err:
        return JsonResponse({'ok': False, 'error': err}, status=403)

    produit = get_object_or_404(Produit, pk=pk, societe=societe)

    # Sécurité supplémentaire : jamais None, toujours un entier
    taux_tva = int(produit.taux_tva_valeur) if produit.taux_tva_valeur is not None else 18

    return JsonResponse({
        'ok': True,
        'designation': produit.designation or '—',
        'prix_ttc': float(produit.prix_vente_tvac or 0),
        'taux_tva': taux_tva,                     # ← garanti entier
        'stock': float(produit.stock_disponible() or 0),
#                                 ↑ Ajoute les ()
    })


@require_http_methods(["GET"])
@login_required
def ajax_info_service(request, pk):
    societe, err = _check_droit(request)
    if err:
        return JsonResponse({'ok': False, 'error': err}, status=403)

    service = get_object_or_404(Service, pk=pk, societe=societe)

    # Même sécurité : jamais None, toujours entier
    taux_tva = int(service.taux_tva.valeur) if service.taux_tva and service.taux_tva.valeur is not None else 18

    return JsonResponse({
        'ok': True,
        'designation': service.designation or '—',
        'prix_ttc': float(service.prix or 0),
        'taux_tva': taux_tva,                     # ← garanti entier
        'stock': '—',
    })

# ──────────────────────────────────────────────
#  AJAX AJOUTER LIGNE — PAS de modif stock ici
# ──────────────────────────────────────────────
@login_required
@require_POST
def ajax_ajouter_ligne(request):
    societe, err = _check_droit(request)
    if err:
        return JsonResponse({'ok': False, 'error': err}, status=403)

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'JSON invalide'}, status=400)

    facture_id = payload.get('facture_id')
    facture = get_object_or_404(Facture, pk=facture_id, societe=societe)

    quantite = Decimal(str(payload.get('quantite', '0'))).quantize(Decimal('0.01'))
    if quantite <= 0:
        return JsonResponse({'ok': False, 'error': 'Quantité invalide (> 0 requise)'}, status=400)

    produit_id = payload.get('produit_id')
    service_id = payload.get('service_id')

    if not (produit_id or service_id):
        return JsonResponse({'ok': False, 'error': 'Produit ou service requis'}, status=400)

    designation = payload.get('designation', '').strip()
    taux_tva = Decimal(str(payload.get('taux_tva', '18'))).quantize(Decimal('0.01'))
    prix_ttc = Decimal(str(payload.get('prix_ttc', '0'))).quantize(Decimal('0.01'))

    produit = None
    service = None
    stock_disponible = 0

    with transaction.atomic():
        if produit_id:
            produit = get_object_or_404(Produit, pk=produit_id, societe=societe)
            designation = produit.designation
            prix_ttc = Decimal(str(produit.prix_vente_tvac))
            taux_tva = Decimal(str(produit.taux_tva_valeur))
            stock_disponible = float(produit.stock_disponible() or 0)

            if quantite > stock_disponible:
                return JsonResponse({
                    'ok': False,
                    'error': f'Stock insuffisant (disponible: {stock_disponible})'
                }, status=400)

        elif service_id:
            service = get_object_or_404(Service, pk=service_id, societe=societe)
            designation = service.designation
            prix_ttc = Decimal(str(service.prix or 0))
            taux_tva = Decimal(str(service.taux_tva.valeur if service.taux_tva else 18))

        # Création de la ligne → SANS les montants calculés (propriétés)
        ligne = LigneFacture.objects.create(
            facture=facture,
            designation=designation or 'Article sans désignation',
            prix_vente_tvac=prix_ttc,
            quantite=quantite,
            taux_tva=taux_tva,
            produit_id=produit_id or None,
            service_id=service_id or None,
        )

        # Les montants sont recalculés automatiquement par les propriétés ou par recalculer_totaux
        facture.recalculer_totaux()

    # Récupération des montants calculés pour la réponse
    return JsonResponse({
        'ok': True,
        'ligne_id': ligne.pk,
        'designation': ligne.designation,
        'quantite': float(ligne.quantite),
        'prix_ttc': float(ligne.prix_vente_tvac),
        'taux_tva': int(ligne.taux_tva),
        'montant_ht': float(ligne.montant_ht),     # ← property calculée
        'montant_tva': float(ligne.montant_tva),   # ← property calculée
        'montant_ttc': float(ligne.montant_ttc),   # ← property calculée
        'total_ht': float(facture.total_ht),
        'total_tva': float(facture.total_tva),
        'total_ttc': float(facture.total_ttc),
        'stock': stock_disponible,
    })
# ──────────────────────────────────────────────
#  AJAX SUPPRIMER LIGNE — PAS de modif stock ici
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
    except:
        return JsonResponse({'ok': False, 'error': 'JSON invalide'}, status=400)

    ligne = get_object_or_404(LigneFacture, pk=ligne_id, facture__societe=societe)
    facture = ligne.facture

    with transaction.atomic():
        ligne.delete()
        facture.recalculer_totaux()

    return JsonResponse({
        'ok': True,
        'total_ht': float(facture.total_ht),
        'total_tva': float(facture.total_tva),
        'total_ttc': float(facture.total_ttc),
    })


# ──────────────────────────────────────────────
#  IMPRESSION A4 (avec QR code)
# ──────────────────────────────────────────────

@login_required
def facture_imprimer_a4(request, pk):
    societe, err = _check_droit(request)
    if err:
        messages.error(request, err)
        return redirect('accueil')

    facture = get_object_or_404(Facture.objects.select_related('client'), pk=pk, societe=societe)
    lignes = facture.lignes.select_related('produit', 'service').all()

    montant_lettres = ''
    try:
        from num2words import num2words
        montant_lettres = num2words(int(facture.total_ttc), lang='fr').capitalize() + ' francs burundais.'
    except:
        pass

    qr_code_url = None
    if facture.invoice_identifier:
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(facture.invoice_identifier)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
        qr_code_url = f"data:image/png;base64,{img_str}"

    return render(request, 'facturer/print_a4.html', {
        'facture': facture,
        'lignes': lignes,
        'societe': _get_societe_info(societe),
        'montant_lettres': montant_lettres,
        'qr_code_url': qr_code_url,
    })


# ──────────────────────────────────────────────
#  IMPRESSION POS
# ──────────────────────────────────────────────

@login_required
def facture_imprimer_pos(request, pk):
    societe, err = _check_droit(request)
    if err:
        messages.error(request, err)
        return redirect('accueil')

    facture = get_object_or_404(Facture.objects.select_related('client'), pk=pk, societe=societe)
    lignes = facture.lignes.select_related('produit', 'service').all()

    montant_lettres = ''
    try:
        from num2words import num2words
        montant_lettres = num2words(int(facture.total_ttc), lang='fr').capitalize() + ' francs burundais.'
    except:
        pass

    return render(request, 'facturer/print_pos.html', {
        'facture': facture,
        'lignes': lignes,
        'societe': _get_societe_info(societe),
        'montant_lettres': montant_lettres,
    })
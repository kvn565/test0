import json
import traceback
from decimal import Decimal
from io import BytesIO
import base64
import logging
import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST, require_http_methods
from django.utils import timezone
from django.template.loader import render_to_string
from django.conf import settings

from weasyprint import HTML

from .models import Devis, LigneDevis, Facture
from .forms import DevisHeaderForm, LigneDevisForm
from produits.models import Produit
from services.models import Service

logger = logging.getLogger(__name__)


def _check_droit(request):
    if request.user.is_superuser:
        return None, "Superadmin n'a pas de société directe."

    societe = getattr(request.user, 'societe', None)
    if not societe:
        return None, "Aucune société associée à votre compte."

    has_right = request.user.droit_devis or request.user.type_poste == 'DIRECTEUR'
    if not has_right:
        return None, "Vous n'avez pas les droits pour accéder aux devis."

    return societe, None


@login_required
def devis_liste(request):
    societe, err = _check_droit(request)
    if err:
        messages.error(request, err)
        return redirect('accueil')

    qs = Devis.objects.filter(societe=societe).select_related('client').order_by('-date_devis', '-id')

    q = request.GET.get('q', '').strip()
    statut = request.GET.get('statut', '')

    if q:
        qs = qs.filter(
            Q(numero__icontains=q) |
            Q(client__nom__icontains=q)
        )
    if statut:
        qs = qs.filter(statut=statut)

    base = Devis.objects.filter(societe=societe)
    stats = {
        'total': base.count(),
        'brouillons': base.filter(statut='BROUILLON').count(),
        'en_attente': base.filter(statut='EN_ATTENTE').count(),
        'valides': base.filter(statut='VALIDE').count(),
    }

    paginator = Paginator(qs, 10)
    page_number = request.GET.get('page', 1)
    devis_page = paginator.get_page(page_number)

    return render(request, 'facturer/devis/liste.html', {
        'devis': devis_page,
        'page_obj': devis_page,
        'stats': stats,
        'header_form': DevisHeaderForm(societe=societe),
        'q': q,
        'statut': statut,
        'statuts': Devis.STATUT_CHOICES,
        'produits_qs': Produit.objects.filter(societe=societe).order_by('designation'),
        'services_qs': Service.objects.filter(societe=societe).order_by('designation'),
    })


@login_required
def devis_detail(request, pk):
    societe, err = _check_droit(request)
    if err:
        messages.error(request, err)
        return redirect('accueil')

    devis = get_object_or_404(
        Devis.objects.select_related('client'),
        pk=pk
    )
    if devis.societe != societe and not request.user.is_superuser:
        messages.error(request, "Vous n'avez pas accès à ce devis.")
        return redirect('facturer:devis_liste')

    lignes = devis.lignes_devis.select_related('produit', 'service').all()

    return render(request, 'facturer/devis/detail.html', {
        'devis': devis,
        'lignes': lignes,
        'produits_qs': Produit.objects.filter(societe=societe).order_by('designation'),
        'services_qs': Service.objects.filter(societe=societe).order_by('designation'),
    })


@login_required
@require_POST
def devis_supprimer(request, pk):
    societe, err = _check_droit(request)
    if err:
        messages.error(request, err)
        return redirect('accueil')

    devis = get_object_or_404(Devis, pk=pk, societe=societe)

    if not devis.peut_etre_supprime:
        messages.error(request, "Impossible de supprimer un devis validé ou transformé.")
        return redirect('facturer:devis_detail', pk=pk)

    num = devis.display_numero
    with transaction.atomic():
        devis.lignes_devis.all().delete()
        devis.delete()

    messages.success(request, f"Devis {num} supprimé avec succès.")
    return redirect('facturer:devis_liste')


@login_required
@require_POST
def ajax_creer_devis(request):
    societe, err = _check_droit(request)
    if err:
        return JsonResponse({'ok': False, 'error': err}, status=403)

    form = DevisHeaderForm(societe=societe, data=request.POST)

    if not form.is_valid():
        return JsonResponse({'ok': False, 'errors': form.errors.get_json_data()}, status=400)

    try:
        with transaction.atomic():
            devis = form.save(commit=False)
            devis.societe = societe
            devis.statut = 'BROUILLON'
            devis.cree_par = request.user
            devis.save()

        return JsonResponse({
            'ok': True,
            'devis_id': devis.pk,
            'message': 'Devis créé'
        })

    except Exception as e:
        logger.exception("Erreur création devis")
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def ajax_ajouter_ligne_devis(request):
    societe, err = _check_droit(request)
    if err:
        return JsonResponse({'ok': False, 'error': err}, status=403)

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({'ok': False, 'error': 'JSON invalide'}, status=400)

    devis_id = payload.get('devis_id')
    if not devis_id:
        return JsonResponse({'ok': False, 'error': 'devis_id manquant'}, status=400)

    devis = get_object_or_404(Devis, pk=devis_id, societe=societe)

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

            if produit_id:
                produit = get_object_or_404(Produit, pk=produit_id, societe=societe)
                if devis.lignes_devis.filter(produit_id=produit_id).exists():
                    return JsonResponse({
                        'ok': False,
                        'error': 'Ce produit est déjà présent dans ce devis.'
                    }, status=400)

                designation = produit.designation
                prix_ttc = Decimal(str(produit.prix_vente_tvac or 0))
                taux_tva = Decimal(str(produit.taux_tva_valeur or 18))
            else:
                service = get_object_or_404(Service, pk=service_id, societe=societe)
                designation = service.designation
                prix_ttc = Decimal(str(service.prix or 0))
                taux_tva = Decimal(str(service.taux_tva.valeur if getattr(service.taux_tva, 'valeur', None) else 18))

            ligne = LigneDevis.objects.create(
                devis=devis,
                designation=designation,
                prix_vente_tvac=prix_ttc,
                quantite=quantite,
                produit=produit,
                service=service,
            )

            devis.recalculer_totaux()
            devis = Devis.objects.get(pk=devis.pk)

    except ValueError as ve:
        return JsonResponse({'ok': False, 'error': str(ve)}, status=400)
    except Exception as e:
        logger.exception(f"Erreur ajout ligne devis {devis_id}")
        return JsonResponse({'ok': False, 'error': 'Erreur serveur lors de l\'ajout'}, status=500)

    return JsonResponse({
        'ok': True,
        'ligne_id': ligne.pk,
        'designation': designation,
        'quantite': float(quantite),
        'prix_ttc': float(prix_ttc),
        'taux_tva': int(taux_tva),
        'total_ht': float(devis.total_ht or 0),
        'total_tva': float(devis.total_tva or 0),
        'total_ttc': float(devis.total_ttc or 0),
        'produit_id': produit.pk if produit else None,
    })


@login_required
@require_POST
def ajax_supprimer_ligne_devis(request):
    societe, err = _check_droit(request)
    if err:
        return JsonResponse({'ok': False, 'error': err}, status=403)

    try:
        data = json.loads(request.body)
        ligne_id = data.get('ligne_id')
    except Exception:
        return JsonResponse({'ok': False, 'error': 'JSON invalide'}, status=400)

    ligne = get_object_or_404(LigneDevis, pk=ligne_id, devis__societe=societe)
    devis = ligne.devis

    try:
        with transaction.atomic():
            ligne.delete()
            devis.recalculer_totaux()
    except Exception as e:
        logger.exception(f"Erreur suppression ligne devis {ligne_id}")
        return JsonResponse({'ok': False, 'error': 'Erreur lors de la suppression'}, status=500)

    return JsonResponse({
        'ok': True,
        'total_ht': float(devis.total_ht),
        'total_tva': float(devis.total_tva),
        'total_ttc': float(devis.total_ttc),
    })


@login_required
@require_POST
def ajax_modifier_ligne_devis(request):
    societe, err = _check_droit(request)
    if err:
        return JsonResponse({'ok': False, 'error': err}, status=403)

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({'ok': False, 'error': 'JSON invalide'}, status=400)

    ligne_id = payload.get('ligne_id')
    if not ligne_id:
        return JsonResponse({'ok': False, 'error': 'ligne_id manquant'}, status=400)

    ligne = get_object_or_404(LigneDevis, pk=ligne_id, devis__societe=societe)
    devis = ligne.devis

    try:
        nouvelle_qte = Decimal(str(payload.get('quantite') or '0')).quantize(Decimal('0.01'))
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Quantité invalide'}, status=400)

    if nouvelle_qte <= 0:
        return JsonResponse({'ok': False, 'error': 'La quantité doit être supérieure à 0'}, status=400)

    try:
        with transaction.atomic():
            ligne.quantite = nouvelle_qte.quantize(Decimal('0.01'))

            prix_tvac = payload.get('prix_tvac')
            if prix_tvac is not None:
                try:
                    ligne.prix_vente_tvac = Decimal(str(prix_tvac))
                except Exception:
                    pass

            ligne.save()
            devis.recalculer_totaux()
    except Exception as e:
        logger.exception(f"Erreur modification ligne devis {ligne_id}")
        return JsonResponse({'ok': False, 'error': 'Erreur lors de la modification'}, status=500)

    return JsonResponse({
        'ok': True,
        'ligne_id': ligne.pk,
        'designation': ligne.designation,
        'quantite': float(nouvelle_qte),
        'prix_ttc': float(ligne.prix_vente_tvac),
        'total_ht': float(devis.total_ht or 0),
        'total_tva': float(devis.total_tva or 0),
        'total_ttc': float(devis.total_ttc or 0),
        'message': 'Ligne modifiée avec succès',
    })


@login_required
@require_POST
def devis_valider(request, pk):
    societe, err = _check_droit(request)
    if err:
        messages.error(request, err)
        return redirect('accueil')

    devis = get_object_or_404(Devis, pk=pk, societe=societe)

    if devis.statut != 'BROUILLON':
        messages.error(request, "Seul un devis en brouillon peut être validé.")
        return redirect('facturer:devis_detail', pk=pk)

    if devis.lignes_devis.count() == 0:
        messages.error(request, "Impossible de valider un devis vide.")
        return redirect('facturer:devis_detail', pk=pk)

    devis.statut = 'EN_ATTENTE'
    devis.save(update_fields=['statut'])
    messages.success(request, f"Devis {devis.display_numero} validé et envoyé au client.")
    return redirect('facturer:devis_detail', pk=pk)


@login_required
@require_POST
def devis_transformer_en_facture(request, pk):
    societe, err = _check_droit(request)
    if err:
        messages.error(request, err)
        return redirect('accueil')

    devis = get_object_or_404(Devis, pk=pk, societe=societe)

    if not devis.peut_etre_transformee:
        messages.error(request, "Seul un devis validé peut être transformé en facture.")
        return redirect('facturer:devis_detail', pk=pk)

    try:
        from .obr_service import envoyer_facture_obr
        from stock.models import SortieStock

        with transaction.atomic():
            facture = Facture.objects.create(
                societe=societe,
                client=devis.client,
                devise=devis.devise,
                applique_tva=devis.applique_tva,
                type_facture='FN',
                statut_obr='EN_ATTENTE',
                cree_par=request.user,
            )

            from .models import LigneFacture

            for ligne in devis.lignes_devis.select_related('produit', 'service', 'taux_tva').all():

                lf = LigneFacture.objects.create(
                    facture=facture,
                    produit=ligne.produit,
                    service=ligne.service,
                    designation=ligne.designation,
                    quantite=ligne.quantite,
                    prix_vente_tvac=ligne.prix_vente_tvac,
                    taux_tva=ligne.taux_tva,
                )

                if ligne.produit:
                    ligne.produit.ajuster_stock(
                        quantite=ligne.quantite,
                        type_facture='FN',
                        facture=facture
                    )

            facture.recalculer_totaux()

            devis.statut = 'TRANSFORME'
            devis.save(update_fields=['statut'])

        facture_url = reverse('facturer:detail', args=[facture.pk])
        messages.success(
            request,
            f"Devis {devis.display_numero} transformé en facture "
            f"<a href='{facture_url}' class='alert-link'>"
            f"{facture.display_numero}</a>."
        )
        return redirect('facturer:devis_detail', pk=pk)

    except Exception as e:
        logger.exception(f"Erreur transformation devis {pk} en facture")
        messages.error(request, f"Erreur lors de la transformation : {str(e)}")
        return redirect('facturer:devis_detail', pk=pk)


@login_required
def devis_imprimer(request, pk):
    societe, err = _check_droit(request)
    if err:
        messages.error(request, err)
        return redirect('accueil')

    devis = get_object_or_404(
        Devis.objects.select_related('client', 'societe'),
        pk=pk, societe=societe
    )

    lignes = devis.lignes_devis.select_related('produit', 'service', 'taux_tva').all()

    montant_lettres = ''
    try:
        from num2words import num2words
        montant_lettres = num2words(
            int(round(devis.total_ttc or 0)), lang='fr'
        ).capitalize() + f" {devis.devise.lower()}."
    except Exception:
        montant_lettres = f"{devis.total_ttc or 0} {devis.devise}"

    context = {
        'devis': devis,
        'lignes': lignes,
        'societe': societe,
        'montant_lettres': montant_lettres,
        'now': timezone.now(),
    }

    html_string = render_to_string('facturer/devis/print.html', context)

    try:
        weasy_html = HTML(string=html_string, base_url=request.build_absolute_uri('/'))
        pdf_dir = os.path.join(settings.MEDIA_ROOT, "devis")
        os.makedirs(pdf_dir, exist_ok=True)
        pdf_path = os.path.join(pdf_dir, "devis.pdf")

        weasy_html.write_pdf(target=pdf_path)

        with open(pdf_path, "rb") as f:
            pdf_data = f.read()

        response = HttpResponse(pdf_data, content_type='application/pdf')
        response['Content-Disposition'] = 'inline; filename="devis.pdf"'
        return response

    except Exception as e:
        logger.exception(f"Erreur PDF devis {pk}")
        messages.error(request, "Erreur lors de la génération du PDF.")
        return redirect('facturer:devis_detail', pk=pk)


@login_required
@require_http_methods(["GET"])
def ajax_info_produit_devis(request, pk):
    societe, err = _check_droit(request)
    if err:
        return JsonResponse({'ok': False, 'error': err}, status=403)

    produit = get_object_or_404(Produit, pk=pk, societe=societe)
    taux_tva = int(produit.taux_tva_valeur) if hasattr(produit, 'taux_tva_valeur') else 18

    return JsonResponse({
        'ok': True,
        'designation': produit.designation or '—',
        'prix_ttc': float(produit.prix_vente_tvac or 0),
        'taux_tva': taux_tva,
    })


@login_required
@require_http_methods(["GET"])
def ajax_info_service_devis(request, pk):
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
    })

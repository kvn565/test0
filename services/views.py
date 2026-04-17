from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from .models import Service
from .forms import ServiceForm


def _check_droit(request):
    societe = getattr(request.user, 'societe', None)
    if not societe:
        return None, "Vous n'êtes rattaché à aucune société."
    type_poste = getattr(request.user, 'type_poste', None)
    if type_poste != 'DIRECTEUR' and not getattr(request.user, 'droit_stock_produit', False):
        return None, "Vous n'avez pas les droits pour gérer les services."
    return societe, None


@login_required
def service_liste(request):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    q        = request.GET.get('q', '')
    statut   = request.GET.get('statut', '')
    page_num = request.GET.get('page', 1)          # ← Ajout pagination

    services = Service.objects.filter(societe=societe).order_by('-date_creation', 'designation')

    if q:
        services = services.filter(designation__icontains=q)
    if statut:
        services = services.filter(statut=statut)

    # ====================== PAGINATION ======================
    paginator = Paginator(services, 5)   # 5 services par page

    try:
        services_page = paginator.page(page_num)
    except PageNotAnInteger:
        services_page = paginator.page(1)
    except EmptyPage:
        services_page = paginator.page(paginator.num_pages)

    return render(request, 'services/liste.html', {
        'services': services_page,          # ← Objet paginé
        'q':        q,
        'statut':   statut,
        'total':    Service.objects.filter(societe=societe).count(),
        'paginator': paginator,             # Pour le template
        'page_obj':  services_page,         # Recommandé
    })


@login_required
def service_creer(request):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    if request.method == 'POST':
        form = ServiceForm(request.POST, societe=societe)
        if form.is_valid():
            service = form.save()
            messages.success(request, f"Service « {service.designation} » créé avec succès.")
            return redirect('services:liste')
    else:
        form = ServiceForm(societe=societe)

    return render(request, 'services/form.html', {
        'form':   form,
        'titre':  'Nouveau service',
        'action': 'Créer',
    })


@login_required
def service_modifier(request, pk):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    service = get_object_or_404(Service, pk=pk, societe=societe)

    if request.method == 'POST':
        form = ServiceForm(request.POST, instance=service, societe=societe)
        if form.is_valid():
            form.save()
            messages.success(request, f"Service « {service.designation} » modifié avec succès.")
            return redirect('services:liste')
    else:
        form = ServiceForm(instance=service, societe=societe)

    return render(request, 'services/form.html', {
        'form':    form,
        'titre':   'Modifier le service',
        'action':  'Enregistrer',
        'service': service,
    })


@login_required
def service_supprimer(request, pk):
    societe, erreur = _check_droit(request)
    if erreur:
        messages.error(request, erreur)
        return redirect('accueil')

    service = get_object_or_404(Service, pk=pk, societe=societe)

    if request.method == 'POST':
        # Protection : vérifier si des lignes de facture utilisent ce service
        nb_lignes = getattr(service, 'lignes_facture', None)
        if nb_lignes and nb_lignes.exists():
            messages.error(request, f"Impossible de supprimer « {service.designation} » : il est utilisé dans des factures.")
            return redirect('services:liste')

        nom = service.designation
        service.delete()
        messages.success(request, f"Service « {nom} » supprimé.")
        return redirect('services:liste')

    return render(request, 'services/supprimer.html', {'service': service})
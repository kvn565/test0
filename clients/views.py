from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from .models import Client, TypeClient
from .forms import ClientForm, TypeClientForm
from .utils.obr_api import check_tin


# ─────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────

def _check_droit(request):
    """Vérifie les droits d'accès au module clients"""
    if request.user.is_superuser:
        return None, "Superadmin n'a pas de société directe."

    societe = getattr(request.user, 'societe', None)
    if not societe:
        return None, "Aucune société associée à votre compte."

    a_droit_facture = (
        request.user.droit_facture_pnb or
        request.user.droit_facture_fdnb or
        request.user.droit_facture_particulier or
        request.user.type_poste == 'DIRECTEUR'
    )

    if not a_droit_facture:
        return None, "Vous n'avez pas les droits nécessaires pour gérer les clients."

    return societe, None


# ─────────────────────────────────────────────────────────────────
#  TYPES DE CLIENT
# ─────────────────────────────────────────────────────────────────

@login_required
def types_clients(request):
    societe, err = _check_droit(request)
    if err:
        messages.error(request, err)
        return redirect('accueil')

    types = TypeClient.objects.filter(societe=societe).order_by('nom')

    return render(request, 'clients/types.html', {
        'types': types,
        'total': types.count(),
    })


@login_required
def creer_type_client(request):
    societe, err = _check_droit(request)
    if err:
        messages.error(request, err)
        return redirect('accueil')

    if request.method == 'POST':
        form = TypeClientForm(societe=societe, data=request.POST)
        if form.is_valid():
            t = form.save()
            messages.success(request, f"✅ Type « {t.nom} » créé avec succès.")
            return redirect('clients:types')
    else:
        form = TypeClientForm(societe=societe)

    return render(request, 'clients/type_form.html', {
        'form': form,
        'titre': 'Nouveau type de client',
        'mode': 'creer',
    })


@login_required
def edit_type_client(request, pk):
    societe, err = _check_droit(request)
    if err:
        messages.error(request, err)
        return redirect('accueil')

    type_client = get_object_or_404(TypeClient, pk=pk, societe=societe)

    if request.method == 'POST':
        form = TypeClientForm(societe=societe, data=request.POST, instance=type_client)
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ Type « {type_client.nom} » modifié avec succès.")
            return redirect('clients:types')
    else:
        form = TypeClientForm(societe=societe, instance=type_client)

    return render(request, 'clients/type_form.html', {
        'form': form,
        'titre': f'Modifier — {type_client.nom}',
        'type_client': type_client,
        'mode': 'modifier',
    })


@login_required
def delete_type_client(request, pk):
    societe, err = _check_droit(request)
    if err:
        messages.error(request, err)
        return redirect('accueil')

    type_client = get_object_or_404(TypeClient, pk=pk, societe=societe)

    if request.method == 'POST':
        if type_client.nb_clients > 0:
            messages.error(
                request,
                f"❌ Impossible de supprimer « {type_client.nom} » : {type_client.nb_clients} client(s) l'utilisent."
            )
            return redirect('clients:types')

        nom = type_client.nom
        type_client.delete()
        messages.success(request, f"✅ Type « {nom} » supprimé avec succès.")
        return redirect('clients:types')

    return render(request, 'clients/type_supprimer.html', {'type_client': type_client})


# ─────────────────────────────────────────────────────────────────
#  CLIENTS
# ─────────────────────────────────────────────────────────────────

@login_required
def liste_clients(request):
    societe, err = _check_droit(request)
    if err:
        messages.error(request, err)
        return redirect('accueil')

    q = request.GET.get('q', '').strip()
    type_filtre = request.GET.get('type', '')
    tva_filtre = request.GET.get('tva', '')
    page_num = request.GET.get('page', 1)

    clients = Client.objects.filter(societe=societe)\
        .select_related('type_client')\
        .order_by('-date_creation', 'nom')

    # Filtres
    if q:
        clients = clients.filter(
            Q(nom__icontains=q) | 
            Q(nif__icontains=q) | 
            Q(adresse__icontains=q)
        )

    if type_filtre:
        clients = clients.filter(type_client_id=type_filtre)

    if tva_filtre == '1':
        clients = clients.filter(assujeti_tva=True)
    elif tva_filtre == '0':
        clients = clients.filter(assujeti_tva=False)

    # Pagination
    paginator = Paginator(clients, 10)   # Je recommande 10 au lieu de 5
    try:
        clients_page = paginator.page(page_num)
    except (PageNotAnInteger, EmptyPage):
        clients_page = paginator.page(1)

    types = TypeClient.objects.filter(societe=societe).order_by('nom')

    return render(request, 'clients/liste.html', {
        'clients': clients_page,
        'types': types,
        'q': q,
        'type_filtre': type_filtre,
        'tva_filtre': tva_filtre,
        'total': Client.objects.filter(societe=societe).count(),
        'paginator': paginator,
        'page_obj': clients_page,
    })


@login_required
def creer_client(request):
    societe, err = _check_droit(request)
    if err:
        messages.error(request, err)
        return redirect('accueil')

    if request.method == 'POST':
        form = ClientForm(societe=societe, data=request.POST)
        if form.is_valid():
            client = form.save()
            messages.success(request, f"✅ Client « {client.nom} » créé avec succès.")
            return redirect('clients:liste')
    else:
        form = ClientForm(societe=societe)

    return render(request, 'clients/form.html', {
        'form': form,
        'titre': 'Nouveau client',
        'mode': 'creer',
    })


@login_required
def edit_client(request, pk):
    societe, err = _check_droit(request)
    if err:
        messages.error(request, err)
        return redirect('accueil')

    client = get_object_or_404(Client, pk=pk, societe=societe)

    if request.method == 'POST':
        form = ClientForm(societe=societe, data=request.POST, instance=client)
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ Client « {client.nom} » modifié avec succès.")
            return redirect('clients:liste')
    else:
        form = ClientForm(societe=societe, instance=client)

    return render(request, 'clients/form.html', {
        'form': form,
        'titre': f'Modifier — {client.nom}',
        'client': client,
        'mode': 'modifier',
    })


@login_required
def delete_client(request, pk):
    societe, err = _check_droit(request)
    if err:
        messages.error(request, err)
        return redirect('accueil')

    client = get_object_or_404(Client, pk=pk, societe=societe)

    if request.method == 'POST':
        if hasattr(client, 'nb_factures') and client.nb_factures > 0:
            messages.error(
                request,
                f"❌ Impossible de supprimer « {client.nom} » : {client.nb_factures} facture(s) associée(s)."
            )
            return redirect('clients:liste')

        nom = client.nom
        client.delete()
        messages.success(request, f"✅ Client « {nom} » supprimé avec succès.")
        return redirect('clients:liste')

    return render(request, 'clients/supprimer.html', {'client': client})


@login_required
@require_POST
def ajax_verifier_nif(request):
    societe, err = _check_droit(request)
    if err:
        return JsonResponse({'ok': False, 'message': err})

    nif = request.POST.get('nif', '').strip()
    if not nif:
        return JsonResponse({'ok': False, 'message': 'Veuillez saisir un NIF valide.'})

    nom_officiel, erreur = check_tin(societe, nif)

    if nom_officiel:
        return JsonResponse({
            'ok': True,
            'nom_officiel': nom_officiel,
            'message': f'Client trouvé : {nom_officiel}'
        })
    else:
        return JsonResponse({
            'ok': False,
            'message': erreur or 'NIF non reconnu par l\'OBR.'
        })
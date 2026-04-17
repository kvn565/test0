# clients/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q

from .models import Client, TypeClient
from .forms import ClientForm, TypeClientForm


# ─────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────

def _check_droit(request):
    """
    Vérifie que l'utilisateur connecté peut accéder au module clients.
    Droit requis : avoir au moins un droit facture, ou être DIRECTEUR.

    Retourne (societe, erreur) — erreur est None si tout est OK.
    """
    if request.user.is_superuser:
        return None, "Superadmin n'a pas de société directe."

    societe = getattr(request.user, 'societe', None)
    if not societe:
        return None, "Aucune société associée à votre compte."

    a_droit_facture = (
        request.user.droit_facture_pnb
        or request.user.droit_facture_fdnb
        or request.user.droit_facture_particulier
        or request.user.type_poste == 'DIRECTEUR'
    )
    if not a_droit_facture:
        return None, "Vous n'avez pas les droits pour gérer les clients."

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

    # ✅ Filtré par société
    types = TypeClient.objects.filter(societe=societe)
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
        'form':  form,
        'titre': 'Nouveau type de client',
        'mode':  'creer',
    })


@login_required
def edit_type_client(request, pk):
    societe, err = _check_droit(request)
    if err:
        messages.error(request, err)
        return redirect('accueil')

    # ✅ Filtre societe → sécurité inter-sociétés
    type_client = get_object_or_404(TypeClient, pk=pk, societe=societe)

    if request.method == 'POST':
        form = TypeClientForm(societe=societe, data=request.POST, instance=type_client)
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ Type « {type_client.nom} » modifié.")
            return redirect('clients:types')
    else:
        form = TypeClientForm(societe=societe, instance=type_client)

    return render(request, 'clients/type_form.html', {
        'form':        form,
        'titre':       f'Modifier — {type_client.nom}',
        'type_client': type_client,
        'mode':        'modifier',
    })


@login_required
def delete_type_client(request, pk):
    societe, err = _check_droit(request)
    if err:
        messages.error(request, err)
        return redirect('accueil')

    type_client = get_object_or_404(TypeClient, pk=pk, societe=societe)

    if request.method == 'POST':
        nb = type_client.nb_clients
        if nb > 0:
            messages.error(
                request,
                f"❌ Impossible de supprimer « {type_client.nom} » : "
                f"{nb} client(s) utilisent ce type."
            )
            return redirect('clients:types')

        nom = type_client.nom
        type_client.delete()
        messages.success(request, f"✅ Type « {nom} » supprimé.")
        return redirect('clients:types')

    return render(request, 'clients/type_supprimer.html', {
        'type_client': type_client,
    })


# ─────────────────────────────────────────────────────────────────
#  CLIENTS
# ─────────────────────────────────────────────────────────────────

@login_required
def liste_clients(request):
    societe, err = _check_droit(request)
    if err:
        messages.error(request, err)
        return redirect('accueil')

    # ✅ Filtre par société
    clients = Client.objects.filter(societe=societe).select_related('type_client')

    q = request.GET.get('q', '').strip()
    if q:
        clients = clients.filter(
            Q(nom__icontains=q) | Q(nif__icontains=q) | Q(adresse__icontains=q)
        )

    # Filtre par type
    type_filtre = request.GET.get('type', '')
    if type_filtre:
        clients = clients.filter(type_client__pk=type_filtre)

    # Filtre TVA
    tva_filtre = request.GET.get('tva', '')
    if tva_filtre == '1':
        clients = clients.filter(assujeti_tva=True)
    elif tva_filtre == '0':
        clients = clients.filter(assujeti_tva=False)

    types = TypeClient.objects.filter(societe=societe)

    return render(request, 'clients/liste.html', {
        'clients':      clients,
        'q':            q,
        'type_filtre':  type_filtre,
        'tva_filtre':   tva_filtre,
        'types':        types,
        'total':        Client.objects.filter(societe=societe).count(),
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
            c = form.save()
            messages.success(request, f"✅ Client « {c.nom} » créé avec succès.")
            return redirect('clients:liste')
    else:
        form = ClientForm(societe=societe)

    return render(request, 'clients/form.html', {
        'form':  form,
        'titre': 'Nouveau client',
        'mode':  'creer',
    })


@login_required
def edit_client(request, pk):
    societe, err = _check_droit(request)
    if err:
        messages.error(request, err)
        return redirect('accueil')

    # ✅ Filtre societe → sécurité inter-sociétés
    client = get_object_or_404(Client, pk=pk, societe=societe)

    if request.method == 'POST':
        form = ClientForm(societe=societe, data=request.POST, instance=client)
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ Client « {client.nom} » modifié.")
            return redirect('clients:liste')
    else:
        form = ClientForm(societe=societe, instance=client)

    return render(request, 'clients/form.html', {
        'form':   form,
        'titre':  f'Modifier — {client.nom}',
        'client': client,
        'mode':   'modifier',
    })


@login_required
def delete_client(request, pk):
    societe, err = _check_droit(request)
    if err:
        messages.error(request, err)
        return redirect('accueil')

    client = get_object_or_404(Client, pk=pk, societe=societe)

    if request.method == 'POST':
        nom = client.nom
        nb  = client.nb_factures
        if nb > 0:
            messages.error(
                request,
                f"❌ Impossible de supprimer « {nom} » : "
                f"{nb} facture(s) associée(s). Archivez-les d'abord."
            )
            return redirect('clients:liste')

        client.delete()
        messages.success(request, f"✅ Client « {nom} » supprimé.")
        return redirect('clients:liste')

    return render(request, 'clients/supprimer.html', {
        'client': client,
    })

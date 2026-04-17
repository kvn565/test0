from django import forms
from datetime import date, datetime
from .models import Facture, LigneFacture
from clients.models import Client
from produits.models import Produit
from services.models import Service


class FactureHeaderForm(forms.ModelForm):
    """
    Modal 1 — En-tête de la facture.
    Reçoit `societe` pour filtrer les clients disponibles.
    """
    class Meta:
        model = Facture
        fields = [
            'date_facture', 'heure_facture', 'client', 'type_facture',
            'bon_commande', 'devise', 'mode_paiement'
        ]
        widgets = {
            'date_facture': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'heure_facture': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'client': forms.Select(attrs={'class': 'form-select'}),
            'type_facture': forms.Select(attrs={'class': 'form-select'}),
            'bon_commande': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'N° bon de commande (optionnel)',
            }),
            'devise': forms.Select(attrs={'class': 'form-select'}),
            'mode_paiement': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, societe=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.societe = societe

        # Filtrer les clients selon la société
        if societe:
            self.fields['client'].queryset = Client.objects.filter(societe=societe).order_by('nom')
        else:
            self.fields['client'].queryset = Client.objects.none()

        self.fields['client'].empty_label = '-- Sélectionner un client --'
        self.fields['bon_commande'].required = False

        # Initialiser date et heure si création
        if not self.instance.pk:
            self.fields['date_facture'].initial = date.today()
            self.fields['heure_facture'].initial = datetime.now().strftime('%H:%M')


class LigneFactureForm(forms.ModelForm):
    """
    Modal 2 — Ligne de détail.
    Reçoit `societe` pour filtrer produits et services.
    """
    class Meta:
        model = LigneFacture
        fields = ['produit', 'service', 'quantite']
        widgets = {
            'produit': forms.Select(attrs={'class': 'form-select', 'id': 'id_ligne_produit'}),
            'service': forms.Select(attrs={'class': 'form-select', 'id': 'id_ligne_service'}),
            'quantite': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01',
                'id': 'id_ligne_quantite',
                'placeholder': '0',
            }),
        }

    def __init__(self, societe=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.societe = societe

        self.fields['produit'].empty_label = '-- Choisir un produit --'
        self.fields['service'].empty_label = '-- Choisir un service --'
        self.fields['produit'].required = False
        self.fields['service'].required = False

        # Filtrer produits et services par société
        if societe:
            self.fields['produit'].queryset = Produit.objects.filter(societe=societe).order_by('designation')
            self.fields['service'].queryset = Service.objects.filter(societe=societe).order_by('designation')
        else:
            self.fields['produit'].queryset = Produit.objects.none()
            self.fields['service'].queryset = Service.objects.none()


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

            if not facture.numero:
                annee = facture.date_facture.year if facture.date_facture else timezone.now().year
                count = Facture.objects.filter(
                    societe=societe,
                    type_facture=facture.type_facture,
                    date_facture__year=annee
                ).count()
                seq = count + 1
                facture.numero = f"{seq:04d}/{annee}"

            facture.save()

            # Validation complète après save
            facture.full_clean()

        return JsonResponse({
            'ok': True,
            'message': 'Facture créée avec succès',
            'facture_id': facture.pk,
            'numero': facture.numero,
        }, status=201)

    except ValidationError as e:
        return JsonResponse({'ok': False, 'errors': e.message_dict}, status=400)
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'ok': False, 'error': 'Erreur interne lors de la création'}, status=500)

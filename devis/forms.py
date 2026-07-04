from datetime import timedelta
from decimal import Decimal

from django import forms
from django.utils import timezone

from clients.models import Client
from taux.models import TauxTVA
from produits.models import Produit
from services.models import Service
from .models import Devis, LigneDevis


class DevisHeaderForm(forms.ModelForm):
    class Meta:
        model = Devis
        fields = ['date_devis', 'date_validite', 'client', 'devise', 'notes']
        widgets = {
            'date_devis': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'date_validite': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'client': forms.Select(attrs={'class': 'form-select'}),
            'devise': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3,
                'placeholder': "Conditions particulières, délais de livraison..."
            }),
        }

    def __init__(self, societe=None, *args, **kwargs):
        self.societe = societe
        super().__init__(*args, **kwargs)
        if societe:
            mode_production = getattr(societe, 'obr_mode_production', False)
            self.fields['client'].queryset = Client.objects.filter(societe=societe, obr_mode_envoye=mode_production).order_by('nom')
        else:
            self.fields['client'].queryset = Client.objects.none()
        self.fields['client'].empty_label = '-- Choisir un client --'
        if not self.instance.pk:
            now = timezone.localtime()
            date_str = now.date().isoformat()
            validite_str = (now.date() + timedelta(days=30)).isoformat()
            self.initial['date_devis'] = date_str
            self.initial['date_validite'] = validite_str
            self.initial['devise'] = 'BIF'

    def clean(self):
        cleaned_data = super().clean()
        client = cleaned_data.get('client')
        if not client:
            self.add_error('client', "Le client est obligatoire.")
        return cleaned_data


class LigneDevisForm(forms.ModelForm):
    class Meta:
        model = LigneDevis
        fields = ['produit', 'service', 'quantite', 'designation', 'prix_vente_tvac', 'taux_tva']
        widgets = {
            'produit': forms.Select(attrs={'class': 'form-select'}),
            'service': forms.Select(attrs={'class': 'form-select'}),
            'quantite': forms.NumberInput(attrs={'class': 'form-control text-end', 'step': '0.001', 'min': '0.001'}),
            'designation': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Désignation'}),
            'prix_vente_tvac': forms.NumberInput(attrs={'class': 'form-control text-end', 'step': '0.001', 'min': '0.001'}),
            'taux_tva': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, societe=None, devis=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.societe = societe
        self.devis = devis
        if societe:
            mode_production = getattr(societe, 'obr_mode_production', False)
            self.fields['produit'].queryset = Produit.objects.filter(societe=societe, obr_mode_envoye=mode_production).order_by('designation')
            self.fields['service'].queryset = Service.objects.filter(societe=societe, obr_mode_envoye=mode_production).order_by('designation')
            if not societe.assujeti_tva:
                self.fields['taux_tva'].queryset = TauxTVA.objects.filter(societe=societe, valeur=Decimal('0.00'), obr_mode_envoye=mode_production)
            else:
                self.fields['taux_tva'].queryset = TauxTVA.objects.for_societe(societe)
        self.fields['produit'].required = False
        self.fields['service'].required = False
        self.fields['designation'].required = False
        self.fields['prix_vente_tvac'].required = True
        self.fields['taux_tva'].required = False


class EmailDevisForm(forms.Form):
    email_destinataire = forms.EmailField(
        label="Email du client",
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'client@exemple.com'}),
    )
    message = forms.CharField(
        label="Message",
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Votre message...'}),
    )

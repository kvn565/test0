# clients/forms.py

from django import forms
from .models import Client, TypeClient


class TypeClientForm(forms.ModelForm):
    """
    Formulaire pour créer/modifier un type de client.
    La société est injectée dans la vue (pas dans le form).
    """
    class Meta:
        model  = TypeClient
        fields = ['nom']
        labels = {'nom': 'Nom du type de client'}
        widgets = {
            'nom': forms.TextInput(attrs={
                'class':       'form-control',      # ✅ CORRIGÉ : était 'form-control-custom'
                'placeholder': 'Ex : Particulier, Entreprise, ONG, Institution...',
                'autofocus':   True,
            }),
        }

    def __init__(self, societe=None, *args, **kwargs):
        self.societe = societe
        super().__init__(*args, **kwargs)

    def clean_nom(self):
        nom = self.cleaned_data.get('nom', '').strip()
        if self.societe:
            qs = TypeClient.objects.filter(societe=self.societe, nom__iexact=nom)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("Ce type de client existe déjà.")
        return nom

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.societe and not obj.pk:
            obj.societe = self.societe
        if commit:
            obj.save()
        return obj


class ClientForm(forms.ModelForm):
    """
    Formulaire client.
    Reçoit `societe` pour filtrer les types de client disponibles.
    """
    class Meta:
        model  = Client
        fields = ['nom', 'nif', 'assujeti_tva', 'adresse', 'type_client']
        labels = {
            'nom':          'Nom du client',
            'nif':          'NIF',
            'assujeti_tva': 'Assujetti TVA',
            'adresse':      'Adresse / Résidence',      # ✅ CORRIGÉ : encodage
            'type_client':  'Type de client',
        }
        widgets = {
            'nom': forms.TextInput(attrs={
                'class':       'form-control',           # ✅ CORRIGÉ
                'placeholder': 'Ex : SODECO SA, Jean Dupont...',
            }),
            'nif': forms.TextInput(attrs={
                'class':       'form-control',
                'placeholder': "Numéro d'Identification Fiscale",  # ✅ CORRIGÉ
            }),
            # ✅ CORRIGÉ : BooleanField → CheckboxInput, pas Select
            'assujeti_tva': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'adresse': forms.TextInput(attrs={
                'class':       'form-control',
                'placeholder': 'Ex : Avenue de la Paix, Bujumbura',
            }),
            'type_client': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, societe=None, *args, **kwargs):
        self.societe = societe
        super().__init__(*args, **kwargs)

        self.fields['nif'].required         = False
        self.fields['adresse'].required     = False
        self.fields['type_client'].required = False
        self.fields['type_client'].empty_label = '-- Sélectionner un type --'  # ✅ CORRIGÉ

        # ✅ CORRIGÉ : filtrer les types par société
        if societe:
            self.fields['type_client'].queryset = (
                TypeClient.objects.filter(societe=societe).order_by('nom')
            )
        else:
            self.fields['type_client'].queryset = TypeClient.objects.none()

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.societe and not obj.pk:
            obj.societe = self.societe
        if commit:
            obj.save()
        return obj

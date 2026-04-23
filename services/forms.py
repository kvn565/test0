# services/forms.py
from django import forms
from .models import Service
from taux.models import Taux

class ServiceForm(forms.ModelForm):

    class Meta:
        model = Service
        fields = ['designation', 'prix_vente', 'taux_tva', 'statut']
        widgets = {
            'designation': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Consultation, Transport, Installation...',
                'autofocus': True,
            }),
            'prix_vente': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00',
            }),
            'taux_tva': forms.Select(attrs={'class': 'form-select'}),
            'statut': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'designation': 'Désignation du service',
            'prix_vente': 'Prix de vente',
            'taux_tva': 'Taux TVA',
            'statut': 'Statut',
        }

    def __init__(self, *args, societe=None, **kwargs):
        """
        Filtre les taux TVA selon la société.
        """
        super().__init__(*args, **kwargs)
        self.societe = societe

        # Taux TVA filtré par société
        if societe:
            self.fields['taux_tva'].queryset = Taux.objects.filter(societe=societe).order_by('valeur')
            self.fields['taux_tva'].empty_label = '-- Sélectionner un taux --'
        else:
            self.fields['taux_tva'].queryset = Taux.objects.none()

    def clean_designation(self):
        """
        Vérifie que la désignation n'existe pas déjà pour cette société.
        """
        designation = self.cleaned_data.get('designation')
        if self.societe:
            qs = Service.objects.filter(societe=self.societe, designation__iexact=designation)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(
                    "Un service avec cette désignation existe déjà pour votre société."
                )
        return designation

    def save(self, commit=True):
        """
        Assigne automatiquement la société avant de sauvegarder.
        """
        obj = super().save(commit=False)
        if self.societe:
            obj.societe = self.societe
        if commit:
            obj.save()
        return obj
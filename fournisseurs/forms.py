# fournisseurs/forms.py
from django import forms
from .models import Fournisseur


class FournisseurForm(forms.ModelForm):

    def __init__(self, *args, societe=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.societe = societe

    class Meta:
        model  = Fournisseur
        fields = ['nom', 'adresse', 'telephone']
        widgets = {
            'nom': forms.TextInput(attrs={
                'class':       'form-control',
                'placeholder': 'Ex: SODECO, BRARUDI...',
                'autofocus':   True,
            }),
            'adresse': forms.TextInput(attrs={
                'class':       'form-control',
                'placeholder': 'Ex: Avenue de la Paix, Bujumbura',
            }),
            'telephone': forms.TextInput(attrs={
                'class':       'form-control',
                'placeholder': 'Ex: +257 22 123 456',
            }),
        }
        labels = {
            'nom':       'Nom du fournisseur',
            'adresse':   'Adresse',
            'telephone': 'Téléphone',
        }

    def clean_nom(self):
        nom = self.cleaned_data.get('nom')
        if self.societe:
            qs = Fournisseur.objects.filter(societe=self.societe, nom__iexact=nom)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("Un fournisseur avec ce nom existe déjà pour votre société.")
        return nom

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.societe:
            obj.societe = self.societe
        if commit:
            obj.save()
        return obj

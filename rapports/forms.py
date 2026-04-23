# rapports/forms.py
from django import forms


class RapportFiltreForm(forms.Form):
    date_debut = forms.DateField(
        required=False,
        label="Date de début",
        widget=forms.DateInput(attrs={
            'type':  'date',
            'class': 'form-control',
        })
    )
    date_fin = forms.DateField(
        required=False,
        label="Date de fin",
        widget=forms.DateInput(attrs={
            'type':  'date',
            'class': 'form-control',
        })
    )
    produit = forms.CharField(
        required=False,
        widget=forms.HiddenInput()
    )
    service = forms.CharField(
        required=False,
        widget=forms.HiddenInput()
    )

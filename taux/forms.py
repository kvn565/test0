# taux/forms.py
from django import forms
from .models import Taux


class TauxForm(forms.ModelForm):

    def __init__(self, *args, societe=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.societe = societe

    class Meta:
        model  = Taux
        fields = ['nom', 'valeur']
        widgets = {
            'nom': forms.TextInput(attrs={
                'class':       'form-control',
                'placeholder': 'Ex: TVA 18%, Exonéré...',
                'autofocus':   True,
            }),
            'valeur': forms.NumberInput(attrs={
                'class':       'form-control',
                'placeholder': 'Ex: 18.00',
                'step':        '0.01',
                'min':         '0',
                'max':         '100',
            }),
        }
        labels = {
            'nom':    'Libellé du taux',
            'valeur': 'Valeur (%)',
        }

    def clean_nom(self):
        nom = self.cleaned_data.get('nom')
        if self.societe:
            qs = Taux.objects.filter(societe=self.societe, nom__iexact=nom)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("Un taux avec ce libellé existe déjà pour votre société.")
        return nom

    def clean_valeur(self):
        valeur = self.cleaned_data.get('valeur')
        if valeur is not None and (valeur < 0 or valeur > 100):
            raise forms.ValidationError("La valeur doit être comprise entre 0 et 100.")
        return valeur

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.societe:
            obj.societe = self.societe
        if commit:
            obj.save()
        return obj

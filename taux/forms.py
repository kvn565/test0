# taux/forms.py
from django import forms
from decimal import Decimal

from .models import TauxTVA   # ← Correction importante


class TauxForm(forms.ModelForm):

    def __init__(self, *args, societe=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.societe = societe

        # Filtrage du queryset si nécessaire (bonnes pratiques)
        if societe:
            self.fields['nom'].widget.attrs.update({
                'placeholder': 'Ex: TVA 18%, Exonéré...',
                'autofocus': True,
            })

    class Meta:
        model = TauxTVA                    # ← Changé de Taux à TauxTVA
        fields = ['nom', 'valeur', 'est_defaut']   # Ajout de est_defaut recommandé
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
            'est_defaut': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
        labels = {
            'nom':        'Libellé du taux',
            'valeur':     'Valeur (%)',
            'est_defaut': 'Taux par défaut',
        }

    def clean_nom(self):
        nom = self.cleaned_data.get('nom')
        if self.societe:
            qs = TauxTVA.objects.filter(societe=self.societe, nom__iexact=nom)
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
        if self.societe and not obj.societe_id:
            obj.societe = self.societe
        if commit:
            obj.save()
        return obj
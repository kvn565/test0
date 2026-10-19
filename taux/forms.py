from django import forms
from decimal import Decimal

from .models import TauxTVA, TauxTC, TauxPFL

TYPE_TAUX_CHOICES = [
    ('TVA', 'TVA — Taxe sur la Valeur Ajoutée'),
    ('TC', 'TC — Taxe de Consommation'),
    ('PFL', 'PFL — Prélèvement Forfaitaire Libératoire'),
]


class TauxForm(forms.ModelForm):

    def __init__(self, *args, societe=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.societe = societe

        if societe:
            self.fields['nom'].widget.attrs.update({
                'placeholder': 'Ex: TVA 18%, Exonéré...',
                'autofocus': True,
            })

    class Meta:
        model = TauxTVA
        fields = ['nom', 'valeur', 'est_defaut']
        widgets = {
            'nom': forms.TextInput(attrs={
                'class':       'form-control',
                'placeholder': 'Ex: TVA 18%, Exonéré...',
                'autofocus':   True,
            }),
            'valeur': forms.NumberInput(attrs={
                'class':       'form-control',
                'placeholder': 'Ex: 18.000',          # Mis à jour
                'step':        '0.001',               # ← Changement principal
                'min':         '0',
                'max':         '100',
                'inputmode':   'decimal',
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
            mode_production = getattr(self.societe, 'obr_mode_production', False)
            qs = TauxTVA.objects.filter(societe=self.societe, nom__iexact=nom, obr_mode_envoye=mode_production)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("Un taux avec ce libellé existe déjà pour votre société.")
        return nom

    def clean_valeur(self):
        valeur = self.cleaned_data.get('valeur')
        if valeur is not None:
            if valeur < 0 or valeur > 100:
                raise forms.ValidationError("La valeur doit être comprise entre 0 et 100.")
            
            # Option importante : normaliser à exactement 3 décimales sans arrondi forcé
            # (troncature ou quantize selon la stratégie choisie précédemment)
            valeur = valeur.quantize(Decimal('0.001'))   # ou Decimal('0.000')
            
        return valeur

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.societe and not obj.societe_id:
            obj.societe = self.societe
        if commit:
            obj.save()
        return obj


class _TauxBaseFormMixin:
    def clean_nom(self):
        nom = self.cleaned_data.get('nom')
        if self.societe:
            mode_production = getattr(self.societe, 'obr_mode_production', False)
            qs = self._meta.model.objects.filter(societe=self.societe, nom__iexact=nom, obr_mode_envoye=mode_production)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("Un taux avec ce libellé existe déjà pour votre société.")
        return nom

    def clean_valeur(self):
        valeur = self.cleaned_data.get('valeur')
        if valeur is not None:
            if valeur < 0 or valeur > 100:
                raise forms.ValidationError("La valeur doit être comprise entre 0 et 100.")
            valeur = valeur.quantize(Decimal('0.001'))
        return valeur

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.societe and not obj.societe_id:
            obj.societe = self.societe
        if commit:
            obj.save()
        return obj


class TauxTCForm(_TauxBaseFormMixin, forms.ModelForm):
    def __init__(self, *args, societe=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.societe = societe
        if societe:
            self.fields['nom'].widget.attrs.update({'placeholder': 'Ex: TC 5%, Exonéré...', 'autofocus': True})

    class Meta:
        model = TauxTC
        fields = ['nom', 'valeur', 'est_defaut']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: TC 5%, Exonéré...', 'autofocus': True}),
            'valeur': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 5.000', 'step': '0.001', 'min': '0', 'max': '100', 'inputmode': 'decimal'}),
            'est_defaut': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {'nom': 'Libellé du taux', 'valeur': 'Valeur (%)', 'est_defaut': 'Taux par défaut'}


class TauxPFLForm(_TauxBaseFormMixin, forms.ModelForm):
    def __init__(self, *args, societe=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.societe = societe
        if societe:
            self.fields['nom'].widget.attrs.update({'placeholder': 'Ex: PFL 2%, Exonéré...', 'autofocus': True})

    class Meta:
        model = TauxPFL
        fields = ['nom', 'valeur', 'est_defaut']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: PFL 2%, Exonéré...', 'autofocus': True}),
            'valeur': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 2.000', 'step': '0.001', 'min': '0', 'max': '100', 'inputmode': 'decimal'}),
            'est_defaut': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {'nom': 'Libellé du taux', 'valeur': 'Valeur (%)', 'est_defaut': 'Taux par défaut'}


FORMS_PAR_TYPE = {'TVA': TauxForm, 'TC': TauxTCForm, 'PFL': TauxPFLForm}
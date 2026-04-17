from django import forms
from django.core.exceptions import ValidationError
from .models import Produit
from categories.models import Categorie
from taux.models import Taux


class ProduitForm(forms.ModelForm):

    class Meta:
        model = Produit
        fields = [
            'categorie', 'code', 'designation', 'unite',
            'prix_vente', 'devise', 'taux_tva', 'statut',
            'reference_dmc', 'rubrique_tarifaire',
            'nombre_par_paquet', 'description_paquet',
        ]
        widgets = {
            'categorie': forms.Select(attrs={'class': 'form-select'}),
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: PROD-001 ou 1001'
            }),
            'designation': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Huile de palme raffinée 5L'
            }),
            'unite': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: litre, kg, pièce, carton'
            }),
            'prix_vente': forms.NumberInput(attrs={
                'class': 'form-control text-end',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'devise': forms.Select(attrs={'class': 'form-select'}),
            'taux_tva': forms.Select(attrs={'class': 'form-select'}),
            'statut': forms.Select(attrs={'class': 'form-select'}),
            'reference_dmc': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: 2025BIPORC91234'
            }),
            'rubrique_tarifaire': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: 15119090000'
            }),
            'nombre_par_paquet': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'step': '1',
                'placeholder': 'Ex: 24 ou 300'
            }),
            'description_paquet': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: carton 24 bouteilles'
            }),
        }

    def __init__(self, *args, societe=None, origine=None, **kwargs):
        # Important : on passe d'abord les données POST avant de modifier les fields
        super().__init__(*args, **kwargs)

        self.societe = societe
        self.origine = origine or (self.instance.origine if self.instance and self.instance.pk else None)

        if societe:
            self.fields['categorie'].queryset = Categorie.objects.filter(societe=societe).order_by('nom')
            self.fields['taux_tva'].queryset = Taux.objects.filter(societe=societe).order_by('valeur')

        # Suppression des champs OBR pour les produits locaux
        if self.origine != 'IMPORTE':
            for field_name in ['reference_dmc', 'rubrique_tarifaire', 'nombre_par_paquet', 'description_paquet']:
                self.fields.pop(field_name, None)

        else:
            # Pour importés : obligatoires
            for field_name in ['reference_dmc', 'rubrique_tarifaire', 'nombre_par_paquet', 'description_paquet']:
                if field_name in self.fields:
                    field = self.fields[field_name]
                    field.required = True
                    field.widget.attrs.update({
                        'required': 'required',
                        'class': field.widget.attrs.get('class', '') + ' border-warning'
                    })

        # Labels (gardé identique à ton style original)
        self.fields['categorie'].label = 'Catégorie *'
        self.fields['code'].label = 'Code produit *'
        self.fields['designation'].label = 'Désignation *'
        self.fields['unite'].label = 'Unité *'
        self.fields['prix_vente'].label = 'Prix de vente *'
        self.fields['devise'].label = 'Devise *'
        self.fields['taux_tva'].label = 'Taux TVA'
        self.fields['statut'].label = 'Statut *'

        if self.origine == 'IMPORTE' and 'reference_dmc' in self.fields:
            self.fields['reference_dmc'].label = 'Référence DMC *'
            self.fields['rubrique_tarifaire'].label = 'Rubrique tarifaire *'
            self.fields['nombre_par_paquet'].label = 'Nombre par paquet *'
            self.fields['description_paquet'].label = 'Description du paquet *'

        # Empty labels
        self.fields['categorie'].empty_label = '— Sélectionner une catégorie —'
        self.fields['taux_tva'].empty_label = '— Sélectionner un taux —'

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code and self.societe:
            qs = Produit.objects.filter(societe=self.societe, code__iexact=code.strip())
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError("Ce code produit existe déjà dans votre société.")
        return code.strip() if code else code

    def clean(self):
        cleaned_data = super().clean()

        if self.origine == 'IMPORTE':
            required_obr = ['reference_dmc', 'rubrique_tarifaire', 'nombre_par_paquet', 'description_paquet']
            missing = []
            for f in required_obr:
                if f in self.fields:
                    val = cleaned_data.get(f)
                    if not val or (isinstance(val, str) and not str(val).strip()):
                        missing.append(self.fields[f].label)
                    elif f == 'nombre_par_paquet' and (val is None or val <= 0):
                        missing.append(self.fields[f].label)

            if missing:
                raise ValidationError(f"Champs obligatoires pour importé : {', '.join(missing)}")

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.societe and not getattr(instance, 'societe_id', None):
            instance.societe = self.societe
        if self.origine:
            instance.origine = self.origine
        if commit:
            instance.save()
        return instance
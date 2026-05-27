from django import forms
from django.core.exceptions import ValidationError
from decimal import Decimal

from django.db import models
from django.db.models import Max
from django.db.models.functions import Cast, Substr

from .models import Produit
from categories.models import Categorie
from taux.models import TauxTVA


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
            'categorie':          forms.Select(attrs={'class': 'form-select'}),
            'code':               forms.TextInput(attrs={'class': 'form-control'}),
            'designation':        forms.TextInput(attrs={'class': 'form-control'}),
            'unite':              forms.TextInput(attrs={'class': 'form-control'}),
            
            # ====================== PRIX AVEC 3 DÉCIMALES ======================
            'prix_vente': forms.NumberInput(attrs={
                'class': 'form-control text-end',
                'step': '0.001',           # ← 3 décimales
                'min': '0',
                'placeholder': '0.000'
            }),
            
            'devise':             forms.Select(attrs={'class': 'form-select'}),
            'taux_tva':           forms.Select(attrs={'class': 'form-select'}),
            'statut':             forms.Select(attrs={'class': 'form-select'}),
            'reference_dmc':      forms.TextInput(attrs={'class': 'form-control'}),
            'rubrique_tarifaire': forms.TextInput(attrs={'class': 'form-control'}),
            'nombre_par_paquet':  forms.NumberInput(attrs={'class': 'form-control'}),
            'description_paquet': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, societe=None, origine=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.societe = societe
        self.origine = origine or getattr(self.instance, 'origine', None)

        # ── Queryset catégories ───────────────────────────────────────────────
        if societe:
            self.fields['categorie'].queryset = (
                Categorie.objects.filter(societe=societe).order_by('nom')
            )

            # Gestion taux TVA
            tous_les_taux = TauxTVA.objects.filter(societe=societe).order_by('valeur')

            if getattr(societe, 'assujeti_tva', False):
                self.taux_qs = tous_les_taux
            else:
                self.taux_qs = tous_les_taux.filter(valeur=Decimal('0.00'))

            self.fields['taux_tva'].queryset = self.taux_qs

            if not self.instance.pk:
                if getattr(societe, 'assujeti_tva', False):
                    taux_defaut = tous_les_taux.filter(est_defaut=True).first() or tous_les_taux.first()
                    if taux_defaut:
                        self.fields['taux_tva'].initial = taux_defaut.pk
                else:
                    taux_zero = self.taux_qs.first()
                    if taux_zero:
                        self.fields['taux_tva'].initial = taux_zero.pk

        self.fields['taux_tva'].empty_label = '— Sélectionner un taux TVA —'

        # Gestion selon origine (LOCAL / IMPORTE)
        if self.origine == 'LOCAL':
            self.fields['code'].widget.attrs.update({
                'readonly': True,
                'style': 'background-color: #e9ecef;',
                'placeholder': 'Généré automatiquement',
            })
            self.fields['code'].help_text = "Code généré automatiquement (ATX1, ATX2, ATX3...)"

            if not self.instance.pk:
                self.fields['code'].initial = self._generer_code_local_form()

            # Supprimer champs importés
            for f in ['reference_dmc', 'rubrique_tarifaire', 'nombre_par_paquet', 'description_paquet']:
                self.fields.pop(f, None)

        else:
            # Produit Importé
            self.fields['code'].widget.attrs.pop('readonly', None)
            self.fields['code'].widget.attrs['style'] = ''
            self.fields['code'].help_text = "Code du produit importé"

            for field_name in ['reference_dmc', 'rubrique_tarifaire', 'nombre_par_paquet', 'description_paquet']:
                if field_name in self.fields:
                    self.fields[field_name].required = True
                    self.fields[field_name].widget.attrs['class'] = (
                        self.fields[field_name].widget.attrs.get('class', '') + ' border-warning'
                    )

        # Labels
        self.fields['prix_vente'].label = 'Prix de vente *'
        self.fields['devise'].label     = 'Devise *'

    # ====================== GÉNÉRATION CODE LOCAL ======================
    def _generer_code_local_form(self):
        if not self.societe:
            return "ATX1"

        prefix = "ATX"
        dernier = (
            Produit.objects
            .filter(societe=self.societe, origine='LOCAL', code__startswith=prefix)
            .annotate(num=Cast(Substr('code', len(prefix) + 1), output_field=models.IntegerField()))
            .aggregate(max_num=Max('num'))['max_num']
        )

        prochain_numero = (dernier or 0) + 1
        return f"{prefix}{prochain_numero}"

    # ── Validations ──────────────────────────────────────────────────────────
    def clean_prix_vente(self):
        prix = self.cleaned_data.get('prix_vente')
        if prix is not None and prix < 0:
            raise ValidationError("Le prix de vente ne peut pas être négatif.")
        return prix

    def clean(self):
        cleaned_data = super().clean()
        # Tes validations existantes...
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.societe and not getattr(instance, 'societe_id', None):
            instance.societe = self.societe
        if self.origine:
            instance.origine = self.origine

        if self.origine == 'LOCAL' and not instance.code:
            instance.code = self._generer_code_local_form()

        if commit:
            instance.save()
        return instance
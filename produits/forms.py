from django import forms
from django.core.exceptions import ValidationError
from decimal import Decimal

# Imports corrigés et complets
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
            'prix_vente':         forms.NumberInput(attrs={
                                      'class': 'form-control text-end',
                                      'step': '0.01', 'min': '0', 'placeholder': '0.00'
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

            # ── Queryset taux TVA ─────────────────────────────────────────────
            tous_les_taux = TauxTVA.objects.filter(societe=societe).order_by('valeur')

            if getattr(societe, 'assujeti_tva', False):
                self.taux_qs = tous_les_taux
            else:
                self.taux_qs = tous_les_taux.filter(valeur=Decimal('0.00'))

            self.fields['taux_tva'].queryset = self.taux_qs

            # Présélection automatique
            if not self.instance.pk:
                if getattr(societe, 'assujeti_tva', False):
                    taux_defaut = tous_les_taux.filter(est_defaut=True).first() or tous_les_taux.first()
                    if taux_defaut:
                        self.fields['taux_tva'].initial = taux_defaut.pk
                else:
                    taux_zero = self.taux_qs.first()
                    if taux_zero:
                        self.fields['taux_tva'].initial = taux_zero.pk

        else:
            self.taux_qs = TauxTVA.objects.none()

        self.fields['taux_tva'].empty_label = '— Sélectionner un taux TVA —'

        # ── Gestion selon origine ─────────────────────────────────────────────
        if self.origine == 'LOCAL':
            self.fields['code'].widget.attrs.update({
                'readonly': True,
                'style': 'background-color: #e9ecef;',
                'placeholder': 'Généré automatiquement',
            })
            self.fields['code'].help_text = "Code généré automatiquement (ATX1, ATX2, ATX3...)"

            if not self.instance.pk:   # Nouveau produit
                self.fields['code'].initial = self._generer_code_local_form()

            # Supprimer les champs spécifiques aux importés
            for f in ['reference_dmc', 'rubrique_tarifaire', 'nombre_par_paquet', 'description_paquet']:
                self.fields.pop(f, None)

        else:
            # Produit Importé
            self.fields['code'].widget.attrs.pop('readonly', None)
            self.fields['code'].widget.attrs['style'] = ''
            self.fields['code'].help_text = "Code du produit importé (souvent = référence DMC)"

            for field_name in ['reference_dmc', 'rubrique_tarifaire', 'nombre_par_paquet', 'description_paquet']:
                if field_name in self.fields:
                    field = self.fields[field_name]
                    field.required = True
                    field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' border-warning'

        # ── Labels ───────────────────────────────────────────────────────────
        self.fields['categorie'].label   = 'Catégorie *'
        self.fields['code'].label        = 'Code produit *'
        self.fields['designation'].label = 'Désignation *'
        self.fields['unite'].label       = 'Unité *'
        self.fields['prix_vente'].label  = 'Prix de vente *'
        self.fields['devise'].label      = 'Devise *'
        self.fields['taux_tva'].label    = 'Taux TVA'
        self.fields['statut'].label      = 'Statut *'
        self.fields['categorie'].empty_label = '— Sélectionner une catégorie —'

        if self.origine == 'IMPORTE':
            self.fields['reference_dmc'].label      = 'Référence DMC *'
            self.fields['rubrique_tarifaire'].label = 'Rubrique tarifaire *'
            self.fields['nombre_par_paquet'].label  = 'Nombre par paquet *'
            self.fields['description_paquet'].label = 'Description du paquet *'

    # ====================== GÉNÉRATION CODE LOCAL ======================
    def _generer_code_local_form(self):
        """Génère ATX1, ATX2, ATX3... de façon fiable"""
        if not self.societe:
            return "ATX1"

        prefix = "ATX"

        dernier = (
            Produit.objects
            .filter(
                societe=self.societe,
                origine='LOCAL',
                code__startswith=prefix
            )
            .annotate(
                num=Cast(Substr('code', len(prefix) + 1), output_field=models.IntegerField())
            )
            .aggregate(max_num=Max('num'))['max_num']
        )

        prochain_numero = (dernier or 0) + 1
        return f"{prefix}{prochain_numero}"

    # ── Validations ──────────────────────────────────────────────────────────
    def clean_taux_tva(self):
        taux = self.cleaned_data.get('taux_tva')
        if self.societe and not getattr(self.societe, 'assujeti_tva', False):
            return self.taux_qs.first()
        return taux

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

        # Sécurité supplémentaire
        if self.origine == 'LOCAL' and not instance.code:
            instance.code = self._generer_code_local_form()

        if commit:
            instance.save()
        return instance
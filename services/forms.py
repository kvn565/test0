from django import forms
from django.core.exceptions import ValidationError
from decimal import Decimal

from .models import Service
from taux.models import TauxTVA


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
                'class': 'form-control text-end',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00',
            }),
            'taux_tva': forms.Select(attrs={'class': 'form-select'}),
            'statut': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, societe=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.societe = societe

        if societe:
            if hasattr(societe, 'assujeti_tva') and not societe.assujeti_tva:
                # Société NON assujettie → Seulement taux 0%
                self.fields['taux_tva'].queryset = TauxTVA.objects.filter(
                    societe=societe,
                    valeur=Decimal('0.00')
                ).order_by('valeur')

                if self.fields['taux_tva'].queryset.exists():
                    self.fields['taux_tva'].initial = self.fields['taux_tva'].queryset.first().id

            else:
                # Société assujettie → Tous les taux de cette société
                self.fields['taux_tva'].queryset = TauxTVA.objects.filter(
                    societe=societe
                ).order_by('valeur')

            self.fields['taux_tva'].empty_label = '— Sélectionner un taux TVA —'

        else:
            self.fields['taux_tva'].queryset = TauxTVA.objects.none()

    # ====================== VALIDATIONS ======================
    def clean_designation(self):
        designation = self.cleaned_data.get('designation')
        if designation and self.societe:
            qs = Service.objects.filter(
                societe=self.societe,
                designation__iexact=designation.strip()
            )
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise ValidationError("Un service avec cette désignation existe déjà pour votre société.")
        
        return designation.strip() if designation else designation

    def clean_prix_vente(self):
        prix = self.cleaned_data.get('prix_vente')
        if prix is not None and prix < 0:
            raise ValidationError("Le prix de vente ne peut pas être négatif.")
        return prix

    def clean(self):
        cleaned_data = super().clean()

        if self.societe and hasattr(self.societe, 'assujeti_tva') and not self.societe.assujeti_tva:
            taux = cleaned_data.get('taux_tva')
            if taux and taux.valeur != Decimal('0.00'):
                self.add_error('taux_tva', "Les sociétés non assujetties ne peuvent utiliser que le taux 0%.")

        return cleaned_data

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.societe and not getattr(obj, 'societe_id', None):
            obj.societe = self.societe
        if commit:
            obj.save()
        return obj
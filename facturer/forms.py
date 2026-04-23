from django import forms
from datetime import date, timedelta
from django.core.exceptions import ValidationError
from decimal import Decimal

from .models import Facture, LigneFacture
from clients.models import Client
from produits.models import Produit
from services.models import Service
from django.utils import timezone


class FactureHeaderForm(forms.ModelForm):
    """
    Formulaire d'en-tête de facture – respecte les exigences OBR
    """
    class Meta:
        model = Facture
        fields = [
            'date_facture', 'heure_facture', 'client', 'type_facture',
            'facture_originale', 'motif_avoir',
            'bon_commande', 'devise', 'mode_paiement'
        ]
        widgets = {
            'date_facture': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'heure_facture': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'client': forms.Select(attrs={'class': 'form-select'}),
            'type_facture': forms.Select(attrs={'class': 'form-select'}),
            'facture_originale': forms.Select(attrs={'class': 'form-select avoir-field'}),
            'motif_avoir': forms.Textarea(attrs={
                'class': 'form-control avoir-field',
                'rows': 3,
                'placeholder': 'Motif obligatoire pour facture d\'avoir...'
            }),
            'bon_commande': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'N° bon de commande (facultatif)'
            }),
            'devise': forms.Select(attrs={'class': 'form-select'}),
            'mode_paiement': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, societe=None, *args, **kwargs):
        self.societe = societe
        super().__init__(*args, **kwargs)

        if societe:
            self.fields['client'].queryset = Client.objects.filter(
                societe=societe
            ).order_by('nom')

            self.fields['facture_originale'].queryset = Facture.objects.filter(
                societe=societe,
                type_facture='FN'
            ).select_related('client').order_by('-date_facture', '-numero')
        else:
            self.fields['client'].queryset = Client.objects.none()
            self.fields['facture_originale'].queryset = Facture.objects.none()

        self.fields['client'].empty_label = '-- Choisir un client --'
        self.fields['facture_originale'].empty_label = '-- Choisir la facture FN concernée --'

        self.fields['bon_commande'].required = False

        # ====================== VALEURS PAR DÉFAUT POUR CRÉATION ======================
        if not self.instance.pk:  # Nouvelle facture
            from django.utils import timezone
            now = timezone.localtime()

            # Correction importante pour le champ date (format YYYY-MM-DD requis par input type="date")
            today_str = now.date().isoformat()  # ex: 2026-04-15
            self.fields['date_facture'].initial = today_str
            self.fields['date_facture'].widget.attrs.update({
                'readonly': 'readonly',
                'style': 'background-color: #e9ecef;',
            })

            self.fields['heure_facture'].initial = now.strftime('%H:%M')
            self.fields['heure_facture'].widget.attrs.update({
                'readonly': 'readonly',
                'style': 'background-color: #e9ecef;',
            })

            self.fields['type_facture'].initial = 'FN'
            self.fields['devise'].initial = 'BIF'
            self.fields['mode_paiement'].initial = 'CAISSE'

        # Classes JS pour FA
        avoir_fields = ['facture_originale', 'motif_avoir']
        for field_name in avoir_fields:
            if field_name in self.fields:
                current = self.fields[field_name].widget.attrs.get('class', '')
                self.fields[field_name].widget.attrs['class'] = f"{current} avoir-field".strip()

        # On enlève le disabled statique
        if 'facture_originale' in self.fields:
            self.fields['facture_originale'].widget.attrs.pop('disabled', None)

    # ====================== VALIDATIONS ======================
    def clean(self):
        cleaned_data = super().clean()
        tf = cleaned_data.get('type_facture')
        client = cleaned_data.get('client')

        if not client:
            self.add_error('client', "Le client est obligatoire pour toute facture.")

        if tf == 'FA':
            fo = cleaned_data.get('facture_originale')
            motif = (cleaned_data.get('motif_avoir') or '').strip()

            if not fo:
                self.add_error('facture_originale', "Une facture d'avoir doit référencer une facture normale (FN).")
            elif fo.type_facture != 'FN':
                self.add_error('facture_originale', "Seule une facture de type FN peut être référencée.")
            elif fo.statut_obr != 'ENVOYE':
                self.add_error('facture_originale', "La facture référencée doit déjà être enregistrée à l'OBR.")

            if not motif:
                self.add_error('motif_avoir', "Le motif est obligatoire pour une facture d'avoir.")

        # Une seule facture EN_ATTENTE autorisée
        if not self.instance.pk and self.societe:
            if Facture.objects.filter(societe=self.societe, statut_obr='EN_ATTENTE').exists():
                raise ValidationError(
                    "Une facture est déjà en attente d'envoi à l'OBR. "
                    "Vous devez d'abord l'envoyer ou l'annuler avant d'en créer une nouvelle."
                )

        return cleaned_data

    def clean_date_facture(self):
        if not self.instance.pk:
            return timezone.now().date()

        date_facture = self.cleaned_data.get('date_facture')
        if not date_facture:
            raise ValidationError("La date de facture est obligatoire.")
        if date_facture > date.today():
            raise ValidationError("La date de facture ne peut pas être dans le futur.")
        if date_facture < date.today() - timedelta(days=365):
            raise ValidationError("La date de facture est trop ancienne (max 1 an).")
        return date_facture

    def clean_heure_facture(self):
        if not self.instance.pk:
            return timezone.now().time()
        heure = self.cleaned_data.get('heure_facture')
        return heure or timezone.now().time()


class LigneFactureForm(forms.ModelForm):
    class Meta:
        model = LigneFacture
        fields = ['produit', 'service', 'quantite', 'designation', 'prix_vente_tvac', 'taux_tva']
        widgets = {
            'produit': forms.Select(attrs={'class': 'form-select'}),
            'service': forms.Select(attrs={'class': 'form-select'}),
            'quantite': forms.NumberInput(attrs={
                'class': 'form-control text-end',
                'step': '0.01',
                'min': '0.01',
            }),
            'designation': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Désignation (auto si produit/service)'
            }),
            'prix_vente_tvac': forms.NumberInput(attrs={
                'class': 'form-control text-end',
                'step': '0.01',
                'min': '0.01',
            }),
            'taux_tva': forms.NumberInput(attrs={
                'class': 'form-control text-end',
                'step': '0.01',
                'min': '0',
                'max': '100',
            }),
        }

    def __init__(self, societe=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.societe = societe

        if societe:
            self.fields['produit'].queryset = Produit.objects.filter(societe=societe).order_by('designation')
            self.fields['service'].queryset = Service.objects.filter(societe=societe).order_by('designation')

        self.fields['produit'].required = False
        self.fields['service'].required = False
        self.fields['designation'].required = False

    def clean_quantite(self):
        q = self.cleaned_data.get('quantite')
        if q is None or q <= 0:
            raise ValidationError("La quantité doit être > 0.")
        return q.quantize(Decimal('0.01'))

    def clean_prix_vente_tvac(self):
        p = self.cleaned_data.get('prix_vente_tvac')
        if p is None or p <= 0:
            raise ValidationError("Le prix TVAC doit être > 0.")
        return p.quantize(Decimal('0.01'))

    def clean_taux_tva(self):
        t = self.cleaned_data.get('taux_tva')
        if t is None:
            raise ValidationError("Le taux TVA est requis.")
        if t < 0 or t > 100:
            raise ValidationError("Taux TVA entre 0 et 100 %.")
        return t.quantize(Decimal('0.01'))

    def clean(self):
        cleaned_data = super().clean()
        produit = cleaned_data.get('produit')
        service = cleaned_data.get('service')

        if not produit and not service:
            raise ValidationError("Sélectionnez un produit OU un service.")

        if produit and service:
            raise ValidationError("Choisissez un produit OU un service (pas les deux).")

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        if instance.produit:
            instance.designation = instance.produit.designation
            instance.prix_vente_tvac = (
                instance.produit.prix_vente_tvac or instance.produit.prix_vente or Decimal('0.00')
            )
            instance.taux_tva = (
                instance.produit.taux_tva.valeur if instance.produit.taux_tva else Decimal('18.00')
            )
        elif instance.service:
            instance.designation = instance.service.designation
            instance.prix_vente_tvac = instance.service.prix or Decimal('0.00')
            instance.taux_tva = (
                instance.service.taux_tva.valeur if instance.service.taux_tva else Decimal('18.00')
            )

        if not instance.designation:
            instance.designation = "Article / Service sans désignation"

        if commit:
            instance.save()
        return instance
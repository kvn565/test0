# facturer/forms.py — VERSION CORRIGÉE ET PROPRE
from decimal import Decimal
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Facture, LigneFacture, Devis, LigneDevis
from clients.models import Client
from produits.models import Produit
from services.models import Service
from taux.models import TauxTVA
from decimal import Decimal, ROUND_DOWN


class FactureHeaderForm(forms.ModelForm):
    class Meta:
        model = Facture
        fields = [
            'date_facture',
            'heure_facture',
            'client',
            'type_facture',
            'facture_originale',
            'motif_avoir',
            'bon_commande',
            'devise',
            'mode_paiement'
        ]
        widgets = {
            'date_facture': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'readonly': 'readonly',
                'tabindex': '-1',
            }),
            'heure_facture': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time',
                'readonly': 'readonly',
                'tabindex': '-1',
            }),
            'client': forms.Select(attrs={'class': 'form-select'}),
            'type_facture': forms.Select(attrs={'class': 'form-select'}),
            'facture_originale': forms.Select(attrs={'class': 'form-select avoir-field'}),
            'motif_avoir': forms.Textarea(attrs={
                'class': 'form-control avoir-field',
                'rows': 3,
                'placeholder': "Motif obligatoire pour facture d'avoir..."
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

        # Valeurs par défaut — injectées comme valeur du champ, pas juste initial
        if not self.instance.pk:
            now = timezone.localtime()
            date_str = now.date().isoformat()
            heure_str = now.strftime('%H:%M')

            # initial sert si aucune donnée POST
            self.fields['date_facture'].initial = date_str
            self.fields['heure_facture'].initial = heure_str
            self.fields['type_facture'].initial = 'FN'
            self.fields['devise'].initial = 'BIF'
            self.fields['mode_paiement'].initial = 'CAISSE'

            # On force aussi la valeur dans les données si pas de POST
            if not self.data:
                self.initial['date_facture'] = date_str
                self.initial['heure_facture'] = heure_str

        for field_name in ['facture_originale', 'motif_avoir']:
            if field_name in self.fields:
                current = self.fields[field_name].widget.attrs.get('class', '')
                self.fields[field_name].widget.attrs['class'] = f"{current} avoir-field".strip()

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
            elif getattr(fo, 'statut_obr', None) != 'ENVOYE':
                self.add_error('facture_originale', "La facture référencée doit déjà être enregistrée à l'OBR.")

            if not motif:
                self.add_error('motif_avoir', "Le motif est obligatoire pour une facture d'avoir.")

        if not self.instance.pk and self.societe:
            if Facture.objects.filter(societe=self.societe, statut_obr='EN_ATTENTE').exists():
                raise ValidationError(
                    "Une facture est déjà en attente d'envoi à l'OBR. "
                    "Vous devez d'abord l'envoyer ou l'annuler avant d'en créer une nouvelle."
                )

        return cleaned_data


# ====================== LIGNE FACTURE ======================
# ====================== LIGNE FACTURE ======================
class LigneFactureForm(forms.ModelForm):
    class Meta:
        model = LigneFacture
        fields = ['produit', 'service', 'quantite', 'designation', 'prix_vente_tvac', 'taux_tva']
        widgets = {
            'produit': forms.Select(attrs={'class': 'form-select'}),
            'service': forms.Select(attrs={'class': 'form-select'}),
            'quantite': forms.NumberInput(attrs={
                'class': 'form-control text-end', 
                'step': '0.001', 
                'min': '0.001'
            }),
            'designation': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Désignation'}),
            'prix_vente_tvac': forms.NumberInput(attrs={
                'class': 'form-control text-end', 
                'step': '0.001', 
                'min': '0.001'
            }),
            'taux_tva': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, societe=None, facture=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.societe = societe
        self.facture = facture   # ← Très important

        if societe:
            self.fields['produit'].queryset = Produit.objects.filter(societe=societe).order_by('designation')
            self.fields['service'].queryset = Service.objects.filter(societe=societe).order_by('designation')

            if not societe.assujeti_tva:
                self.fields['taux_tva'].queryset = TauxTVA.objects.filter(
                    societe=societe, valeur=Decimal('0.00')
                )
            else:
                self.fields['taux_tva'].queryset = TauxTVA.objects.for_societe(societe)

        self.fields['produit'].required = False
        self.fields['service'].required = False
        self.fields['designation'].required = False
        self.fields['prix_vente_tvac'].required = True
        self.fields['taux_tva'].required = False  # ← Ajouté: géré par le modèle

        def clean(self):
            cleaned_data = super().clean()
            produit = cleaned_data.get('produit')
            service = cleaned_data.get('service')
            quantite = cleaned_data.get('quantite')
            prix_tvac = cleaned_data.get('prix_vente_tvac')

            if not produit and not service:
                raise ValidationError("Vous devez sélectionner un produit OU un service.")

            if produit and service:
                raise ValidationError("Choisissez soit un produit, soit un service.")

            # ====================== TRONCATURE À 3 DÉCIMALES ======================
            if quantite is not None:
                cleaned_data['quantite'] = quantite.quantize(Decimal('0.001'), rounding=ROUND_DOWN)

            if prix_tvac is not None:
                cleaned_data['prix_vente_tvac'] = prix_tvac.quantize(Decimal('0.001'), rounding=ROUND_DOWN)
            # =====================================================================

            # ====================== ANTI-DOUBLON PRODUIT ======================
            if self.facture and produit:
                qs = LigneFacture.objects.filter(
                    facture=self.facture,
                    produit=produit
                )
                if self.instance and self.instance.pk:
                    qs = qs.exclude(pk=self.instance.pk)

                if qs.exists():
                    raise ValidationError({
                        'produit': f"Le produit « {produit.designation} » est déjà présent dans cette facture."
                    })

            return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        # === CORRECTION CRITIQUE ===
        if self.facture:
            instance.facture = self.facture
        else:
            raise ValidationError("La facture est obligatoire pour ajouter une ligne.")

        # Auto-remplissage de la désignation
        if instance.produit:
            instance.designation = instance.produit.designation
        elif instance.service:
            instance.designation = instance.service.designation
        elif not instance.designation:
            instance.designation = "Article divers"

        if commit:
            instance.save()

        return instance


# ====================== DEVIS ======================
class DevisHeaderForm(forms.ModelForm):
    class Meta:
        model = Devis
        fields = [
            'date_devis',
            'date_validite',
            'client',
            'devise',
            'notes',
        ]
        widgets = {
            'date_devis': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'date_validite': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'client': forms.Select(attrs={'class': 'form-select'}),
            'devise': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': "Conditions particulières, délais de livraison..."
            }),
        }

    def __init__(self, societe=None, *args, **kwargs):
        self.societe = societe
        super().__init__(*args, **kwargs)

        if societe:
            self.fields['client'].queryset = Client.objects.filter(
                societe=societe
            ).order_by('nom')
        else:
            self.fields['client'].queryset = Client.objects.none()

        self.fields['client'].empty_label = '-- Choisir un client --'

        if not self.instance.pk:
            now = timezone.localtime()
            date_str = now.date().isoformat()
            validite_str = (now.date() + timezone.timedelta(days=30)).isoformat()

            self.fields['date_devis'].initial = date_str
            self.fields['date_validite'].initial = validite_str
            self.fields['devise'].initial = 'BIF'

            if not self.data:
                self.initial['date_devis'] = date_str
                self.initial['date_validite'] = validite_str

    def clean(self):
        cleaned_data = super().clean()
        client = cleaned_data.get('client')
        if not client:
            self.add_error('client', "Le client est obligatoire.")
        return cleaned_data


class LigneDevisForm(forms.ModelForm):
    class Meta:
        model = LigneDevis
        fields = ['produit', 'service', 'quantite', 'designation', 'prix_vente_tvac', 'taux_tva']
        widgets = {
            'produit': forms.Select(attrs={'class': 'form-select'}),
            'service': forms.Select(attrs={'class': 'form-select'}),
            'quantite': forms.NumberInput(attrs={
                'class': 'form-control text-end', 'step': '0.001', 'min': '0.001'
            }),
            'designation': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Désignation'}),
            'prix_vente_tvac': forms.NumberInput(attrs={
                'class': 'form-control text-end', 'step': '0.001', 'min': '0.001'
            }),
            'taux_tva': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, societe=None, devis=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.societe = societe
        self.devis = devis

        if societe:
            self.fields['produit'].queryset = Produit.objects.filter(societe=societe).order_by('designation')
            self.fields['service'].queryset = Service.objects.filter(societe=societe).order_by('designation')

            if not societe.assujeti_tva:
                self.fields['taux_tva'].queryset = TauxTVA.objects.filter(
                    societe=societe, valeur=Decimal('0.00')
                )
            else:
                self.fields['taux_tva'].queryset = TauxTVA.objects.for_societe(societe)

        self.fields['produit'].required = False
        self.fields['service'].required = False
        self.fields['designation'].required = False
        self.fields['prix_vente_tvac'].required = True
        self.fields['taux_tva'].required = False

    def clean(self):
        cleaned_data = super().clean()
        produit = cleaned_data.get('produit')
        service = cleaned_data.get('service')
        quantite = cleaned_data.get('quantite')
        prix_tvac = cleaned_data.get('prix_vente_tvac')

        if not produit and not service:
            raise ValidationError("Vous devez sélectionner un produit OU un service.")

        if produit and service:
            raise ValidationError("Choisissez soit un produit, soit un service.")

        if quantite is not None:
            cleaned_data['quantite'] = quantite.quantize(Decimal('0.001'), rounding=ROUND_DOWN)

        if prix_tvac is not None:
            cleaned_data['prix_vente_tvac'] = prix_tvac.quantize(Decimal('0.001'), rounding=ROUND_DOWN)

        if self.devis and produit:
            qs = LigneDevis.objects.filter(devis=self.devis, produit=produit)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError({
                    'produit': f"Le produit « {produit.designation} » est déjà présent dans ce devis."
                })

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        if self.devis:
            instance.devis = self.devis
        else:
            raise ValidationError("Le devis est obligatoire pour ajouter une ligne.")

        if instance.produit:
            instance.designation = instance.produit.designation
        elif instance.service:
            instance.designation = instance.service.designation
        elif not instance.designation:
            instance.designation = "Article divers"

        if commit:
            instance.save()

        return instance
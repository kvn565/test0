# stock/forms.py
from django import forms
from django.db.models import Sum
from datetime import date
import time
from .models import EntreeStock, SortieStock
from produits.models import Produit
from fournisseurs.models import Fournisseur


class EntreeStockForm(forms.ModelForm):

    def __init__(self, *args, societe=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.societe = societe

        self.fields['fournisseur'].empty_label = '-- Sélectionner un fournisseur --'
        self.fields['produit'].empty_label     = '-- Sélectionner un produit --'
        self.fields['fournisseur'].required    = False
        self.fields['numero_ref'].required     = False

        if not self.instance.pk:
            from django.utils import timezone
            self.fields['date_entree'].initial = timezone.now().date().isoformat()
            # Génération automatique d'un numero_ref unique
            self.fields['numero_ref'].initial = f"REF-{int(time.time() * 1000)}"

        # Filtrer par société
        if societe:
            self.fields['produit'].queryset     = Produit.objects.filter(societe=societe).order_by('designation')
            self.fields['fournisseur'].queryset = Fournisseur.objects.filter(societe=societe).order_by('nom')
        else:
            self.fields['produit'].queryset     = Produit.objects.none()
            self.fields['fournisseur'].queryset = Fournisseur.objects.none()

    class Meta:
        model  = EntreeStock
        fields = ['type_entree', 'numero_ref', 'date_entree', 'produit', 'fournisseur',
                  'quantite', 'prix_revient', 'prix_vente_actuel']
        widgets = {
            'type_entree':       forms.Select(attrs={'class': 'form-select'}),
            'numero_ref':        forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: REQ-2025-001',
            }),
            'date_entree':       forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'produit':           forms.Select(attrs={'class': 'form-select', 'id': 'id_produit'}),
            'fournisseur':       forms.Select(attrs={'class': 'form-select'}),
            'quantite':          forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.01', 'min': '0',
            }),
            'prix_revient':      forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.01', 'min': '0', 'id': 'id_prix_revient',
            }),
            'prix_vente_actuel': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.01', 'min': '0',
            }),
        }

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.societe:
            obj.societe = self.societe
        # Assurer que numero_ref n'est jamais vide
        if not obj.numero_ref:
            obj.numero_ref = f"REF-{int(time.time() * 1000)}"
        if commit:
            obj.save()
        return obj


class SortieStockForm(forms.ModelForm):

    def __init__(self, *args, societe=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.societe = societe

        self.fields['code'].required        = False
        self.fields['commentaire'].required = False

        if not self.instance.pk:
            self.fields['date_sortie'].initial = date.today()

        # Filtrer les entrées stock par société
        if societe:
            self.fields['entree_stock'].queryset = (
                EntreeStock.objects.filter(societe=societe)
                .select_related('produit')
                .order_by('produit__designation')
            )
        else:
            self.fields['entree_stock'].queryset = EntreeStock.objects.none()

        self.fields['entree_stock'].empty_label = '-- Rechercher un produit en stock --'

    class Meta:
        model  = SortieStock
        fields = ['type_sortie', 'code', 'date_sortie', 'entree_stock', 'quantite', 'prix', 'commentaire']
        widgets = {
            'type_sortie':  forms.Select(attrs={'class': 'form-select'}),
            'code':         forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: SORT-2025-001',
            }),
            'date_sortie':  forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'entree_stock': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_entree_stock',
            }),
            'quantite':     forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01', 'min': '0.01',
                'id': 'id_quantite_sortie',
            }),
            'prix':         forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01', 'min': '0',
                'id': 'id_prix_sortie',
            }),
            'commentaire':  forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Expliquez la raison de la sortie...',
            }),
        }
        labels = {
            'type_sortie':  "Type de sortie",
            'code':         "Code sortie",
            'date_sortie':  "Date de sortie",
            'entree_stock': "Recherche produit en stock",
            'quantite':     "Quantité à sortir",
            'prix':         "Prix unitaire",
            'commentaire':  "Commentaire / Explication",
        }

    def clean(self):
        cleaned_data = super().clean()
        entree = cleaned_data.get('entree_stock')
        qte    = cleaned_data.get('quantite')
        if entree and qte:
            total_sorti = SortieStock.objects.filter(
                entree_stock=entree
            ).exclude(
                pk=self.instance.pk if self.instance.pk else None
            ).aggregate(total=Sum('quantite'))['total'] or 0
            dispo = entree.quantite - total_sorti
            if qte > dispo:
                self.add_error('quantite',
                    f"Quantité insuffisante. Stock disponible : {dispo} {entree.produit.unite}.")
        return cleaned_data

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.societe:
            obj.societe = self.societe
        if commit:
            obj.save()
        return obj
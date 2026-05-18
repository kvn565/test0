from django import forms
from decimal import Decimal
from django.utils import timezone

from .models import EntreeStock, SortieStock
from produits.models import Produit
from fournisseurs.models import Fournisseur


# ===================================================================
# ====================== FORMULAIRE ENTREE STOCK ======================
# ===================================================================

class EntreeStockForm(forms.ModelForm):

    def __init__(self, *args, societe=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.societe = societe

        self.fields['fournisseur'].empty_label = '-- Sélectionner un fournisseur --'
        self.fields['produit'].empty_label = '-- Sélectionner un produit --'
        self.fields['fournisseur'].required = False

        # ====================== NUMERO DE REFERENCE AUTOMATIQUE ======================
        if not self.instance.pk:  # Nouvelle entrée uniquement
            self.fields['numero_ref'].initial = self.generer_numero_reference(societe)
            self.fields['numero_ref'].widget.attrs['readonly'] = True

        # Date automatique et verrouillée
        date_aujourd_hui = timezone.now().date().isoformat()
        self.fields['date_entree'].widget = forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'readonly': 'readonly',
            'value': date_aujourd_hui,
            'style': 'background-color:#e9ecef; cursor:not-allowed;',
        })

        if not self.instance.pk:
            self.fields['date_entree'].initial = timezone.now().date()

        if societe:
            self.fields['fournisseur'].queryset = Fournisseur.objects.filter(societe=societe).order_by('nom')

            produits = Produit.objects.filter(societe=societe, statut='ACTIF').order_by('designation')
            self.fields['produit'].choices = [('', '-- Sélectionner un produit --')] + [
                (p.pk, f"{p.designation} ({p.code})") for p in produits
            ]
            self.fields['produit'].widget.attrs.update({
                'class': 'form-select',
                'id': 'id_produit',
                'onchange': 'chargerPrixDepuisProduit(this.value)',  
            })

        if not self.instance.pk:
            self.fields['prix_revient'].initial = Decimal('0.00')
            self.fields['prix_vente_actuel'].initial = Decimal('0.00')

    def generer_numero_reference(self, societe):
        """Génère un numéro de référence automatique unique pour les entrées"""
        if not societe:
            return "ENT-1"
        
        today = timezone.now().date().strftime("%Y%m%d")
        prefix = f"ENT-{today}"
        
        dernier = EntreeStock.objects.filter(
            societe=societe, 
            numero_ref__startswith=prefix
        ).order_by('-numero_ref').first()

        if dernier and dernier.numero_ref:
            try:
                num = int(dernier.numero_ref.split('-')[-1]) + 1
            except ValueError:
                num = 1
        else:
            num = 1

        return f"{prefix}-{num}"   # Format : ENT-20250511-1

    class Meta:
        model = EntreeStock
        fields = ['type_entree', 'numero_ref', 'date_entree', 'produit',
                  'fournisseur', 'quantite', 'prix_revient', 'prix_vente_actuel']

        widgets = {
            'type_entree':       forms.Select(attrs={'class': 'form-select'}),
            'numero_ref':        forms.TextInput(attrs={'class': 'form-control'}),
            'date_entree':       forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'produit':           forms.Select(attrs={'class': 'form-select'}),
            'fournisseur':       forms.Select(attrs={'class': 'form-select'}),
            'quantite':          forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'prix_revient':      forms.NumberInput(attrs={'class': 'form-control text-end', 'step': '0.001'}),
            'prix_vente_actuel': forms.NumberInput(attrs={'class': 'form-control text-end', 'step': '0.001'}),
        }


# ===================================================================
# ====================== FORMULAIRE SORTIE STOCK ======================
# ===================================================================

class SortieStockForm(forms.ModelForm):

    def __init__(self, *args, societe=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.societe = societe

        # Code sortie automatique
        if not self.instance.pk:
            self.fields['code'].initial = self.generer_code_sortie(societe)
            self.fields['code'].widget.attrs['readonly'] = True

        # Date automatique
        date_aujourd_hui = timezone.now().date().isoformat()
        self.fields['date_sortie'].widget = forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'readonly': 'readonly',
            'value': date_aujourd_hui,
            'style': 'background-color:#e9ecef; cursor:not-allowed;',
        })

        if societe:
            queryset = EntreeStock.objects.filter(
                societe=societe,
                quantite__gt=0
            ).select_related('produit').order_by('produit__designation')

            self.fields['entree_stock'].queryset = queryset

            self.fields['entree_stock'].widget.attrs.update({
                'onchange': 'chargerPrixDepuisEntree(this.value)',
                'id': 'id_entree_stock',
                'class': 'form-select'
            })

        self.fields['entree_stock'].empty_label = '-- Sélectionner un produit en stock --'

        # Prix en lecture seule
        self.fields['prix'].widget.attrs.update({
            'readonly': 'readonly',
            'style': 'background-color:#e9ecef; text-align: right;',
            'id': 'id_prix'
        })

    def generer_code_sortie(self, societe):
        if not societe:
            return "SORT-1"
        
        today = timezone.now().date().strftime("%Y%m%d")
        prefix = f"SORT-{today}"
        
        dernier = SortieStock.objects.filter(
            societe=societe, code__startswith=prefix
        ).order_by('-code').first()

        if dernier and dernier.code:
            try:
                num = int(dernier.code.split('-')[-1]) + 1
            except ValueError:
                num = 1
        else:
            num = 1

        return f"{prefix}-{num}"

    class Meta:
        model = SortieStock
        fields = ['type_sortie', 'code', 'date_sortie', 'entree_stock', 
                  'quantite', 'prix', 'commentaire']
        
        widgets = {
            'type_sortie':  forms.Select(attrs={'class': 'form-select'}),
            'code':         forms.TextInput(attrs={'class': 'form-control'}),
            'date_sortie':  forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'entree_stock': forms.Select(attrs={'class': 'form-select'}),
            'quantite':     forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'prix':         forms.NumberInput(attrs={
                'class': 'form-control text-end',
                'step': '0.001',
                'id': 'id_prix'
            }),
            'commentaire':  forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3, 
                'placeholder': 'Motif de la sortie...'
            }),
        }

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.societe:
            obj.societe = self.societe

        if not obj.prix and obj.entree_stock:
            obj.prix = obj.entree_stock.prix_vente_actuel or getattr(obj.entree_stock.produit, 'prix_vente', Decimal('0.00'))

        if commit:
            obj.save()
        return obj
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

        # Configuration des champs select
        self.fields['fournisseur'].empty_label = '-- Sélectionner un fournisseur --'
        self.fields['fournisseur'].required = False

        # ====================== NUMERO REFERENCE AUTOMATIQUE ======================
        if not self.instance.pk:  # Seulement pour une nouvelle entrée
            self.fields['numero_ref'].initial = self.generer_numero_reference(societe)
            self.fields['numero_ref'].widget.attrs['readonly'] = True
            self.fields['numero_ref'].widget.attrs['style'] = 'background-color:#e9ecef; font-weight:bold;'

            self.fields['date_entree'].initial = timezone.now().date()

        # Configuration du champ date
        self.fields['date_entree'].widget.attrs.update({
            'class': 'form-control',
            'type': 'date',
            'readonly': 'readonly',
            'style': 'background-color:#e9ecef; cursor:not-allowed; font-weight:bold;',
        })

        # Champs en lecture seule
        readonly_fields = ['prix_vente_actuel']
        for field_name in readonly_fields:
            if field_name in self.fields:
                self.fields[field_name].widget.attrs.update({
                    'readonly': 'readonly',
                    'style': 'background-color:#e9ecef; font-weight:bold; cursor:not-allowed;',
                })

        # Filtrage par société
        if societe:
            self.fields['fournisseur'].queryset = Fournisseur.objects.filter(societe=societe).order_by('nom')

            self.fields['produit'].queryset = Produit.objects.filter(
                societe=societe, statut='ACTIF'
            ).order_by('designation')
            
            self.fields['produit'].empty_label = '-- Sélectionner un produit --'
            self.fields['produit'].widget.attrs.update({
                'class': 'form-select',
                'id': 'id_produit',
                'onchange': 'chargerPrixDepuisProduit(this.value)',
            })

        if not self.instance.pk:
            self.fields['prix_revient'].initial = Decimal('0.000')
            self.fields['prix_vente_actuel'].initial = Decimal('0.000')

    # ====================== NETTOYAGE ======================
    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get('produit'):
            self.add_error('produit', "Le produit est obligatoire.")
        return cleaned_data

    def clean_date_entree(self):
        return timezone.now().date() if not self.instance.pk else self.cleaned_data.get('date_entree')

    # ====================== GÉNÉRATION NUMERO REFERENCE ======================
    def generer_numero_reference(self, societe):
        """Génère un numéro de référence automatique pour les entrées stock"""
        if not societe:
            return "ENT-1"

        today_str = timezone.now().date().strftime("%Y%m%d")
        prefix = f"ENT-{today_str}"

        dernier = EntreeStock.objects.filter(
            societe=societe,
            numero_ref__startswith=prefix
        ).order_by('-numero_ref').first()

        if dernier and dernier.numero_ref:
            try:
                last_num = int(dernier.numero_ref.split('-')[-1])
                new_num = last_num + 1
            except ValueError:
                new_num = 1
        else:
            new_num = 1

        return f"{prefix}-{new_num}"   # Format : ENT-20250527-1

    def save(self, commit=True):
        obj = super().save(commit=False)
        
        if self.societe:
            obj.societe = self.societe

        # ====================== DEVISE & PRIX (Sécurisé) ======================
        if obj.produit_id:
            obj.devise = obj.produit.devise
            
            if not obj.prix_vente_actuel or obj.prix_vente_actuel == 0:
                obj.prix_vente_actuel = obj.produit.prix_vente_tvac or Decimal('0.000')

        if commit:
            obj.save()
        return obj

    class Meta:
        model = EntreeStock
        fields = ['type_entree', 'numero_ref', 'date_entree', 'produit',
                  'fournisseur', 'quantite', 'prix_revient', 
                  'prix_vente_actuel', 'commentaire']
        
        widgets = {
            'type_entree': forms.Select(attrs={'class': 'form-select'}),
            'numero_ref': forms.TextInput(attrs={'class': 'form-control'}),
            'date_entree': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'produit': forms.Select(attrs={'class': 'form-select'}),
            'fournisseur': forms.Select(attrs={'class': 'form-select'}),
            'quantite': forms.NumberInput(attrs={'class': 'form-control text-end', 'step': '0.001', 'min': '0.001'}),
            'prix_revient': forms.NumberInput(attrs={'class': 'form-control text-end', 'step': '0.001', 'min': '0.000'}),
            'prix_vente_actuel': forms.NumberInput(attrs={'class': 'form-control text-end', 'step': '0.001'}),
        }

# ===================================================================


class SortieStockForm(forms.ModelForm):

    def __init__(self, *args, societe=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.societe = societe

        # ====================== CODE SORTIE AUTOMATIQUE ======================
        if not self.instance.pk:  # Seulement pour les nouvelles sorties
            self.fields['code'].initial = self.generer_code_sortie(societe)
            self.fields['code'].widget.attrs['readonly'] = True
            self.fields['code'].widget.attrs['style'] = 'background-color:#e9ecef; font-weight:bold;'

        # Date automatique
        if not self.instance.pk:
            self.fields['date_sortie'].initial = timezone.now().date()

        self.fields['date_sortie'].widget.attrs.update({
            'class': 'form-control',
            'type': 'date',
            'readonly': 'readonly',
            'style': 'background-color:#e9ecef; cursor:not-allowed; font-weight:bold;',
        })

        # Filtrage des produits en stock
        if societe:
            queryset = EntreeStock.objects.filter(
                societe=societe,
                quantite__gt=0
            ).select_related('produit')

            # Label propre du select (Produit + Quantité disponible)
            choices = []
            for entree in queryset:
                designation = entree.produit.designation
                qte_dispo = getattr(entree, 'quantite_disponible', entree.quantite)
                unite = getattr(entree.produit, 'unite', '')
                
                label = f"{designation} — {qte_dispo:.3f} {unite}"
                choices.append((entree.pk, label))

            self.fields['entree_stock'].queryset = queryset
            self.fields['entree_stock'].widget.choices = choices

            self.fields['entree_stock'].widget.attrs.update({
                'onchange': 'chargerPrixDepuisEntree(this.value)',
                'id': 'id_entree_stock',
                'class': 'form-select'
            })

        self.fields['entree_stock'].empty_label = '-- Sélectionner un produit en stock --'

    # ====================== VALIDATION ======================
    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get('entree_stock'):
            self.add_error('entree_stock', "Le produit en stock est obligatoire.")
        if not cleaned_data.get('quantite'):
            self.add_error('quantite', "La quantité est obligatoire.")
        return cleaned_data

    def clean_date_sortie(self):
        if not self.instance.pk:
            return timezone.now().date()
        return self.cleaned_data.get('date_sortie')

    # ====================== GÉNÉRATION DU CODE SORTIE ======================
    def generer_code_sortie(self, societe):
        if not societe:
            return "SORT-1"

        today_str = timezone.now().date().strftime("%Y%m%d")
        prefix = f"SORT-{today_str}"

        dernier = SortieStock.objects.filter(
            societe=societe,
            code__startswith=prefix
        ).order_by('-code').first()

        if dernier and dernier.code:
            try:
                # Récupérer le dernier numéro après le tiret
                last_num = int(dernier.code.split('-')[-1])
                new_num = last_num + 1
            except ValueError:
                new_num = 1
        else:
            new_num = 1

        return f"{prefix}-{new_num}"   # ← Format souhaité : SORT-20250525-1

    # ====================== SAVE ======================
    def save(self, commit=True):
        obj = super().save(commit=False)
        
        if self.societe:
            obj.societe = self.societe

        if not self.instance.pk:
            obj.date_sortie = timezone.now().date()

        # Devise automatique
        if obj.entree_stock_id:
            obj.devise = obj.entree_stock.devise
            if not obj.prix or obj.prix == 0:
                obj.prix = obj.entree_stock.prix_vente_actuel or Decimal('0.000')

        if commit:
            obj.save()
        return obj

    class Meta:
        model = SortieStock
        fields = ['type_sortie', 'code', 'date_sortie', 'entree_stock', 
                  'quantite', 'prix', 'commentaire']
        widgets = {
            'type_sortie': forms.Select(attrs={'class': 'form-select'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'date_sortie': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'entree_stock': forms.Select(attrs={'class': 'form-select'}),
            'quantite': forms.NumberInput(attrs={
                'class': 'form-control text-end',
                'step': '0.001',
                'min': '0.001'
            }),
            'prix': forms.NumberInput(attrs={
                'class': 'form-control text-end',
                'step': '0.001',
                'id': 'id_prix',
                'readonly': 'readonly'
            }),
            'commentaire': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3, 
                'placeholder': 'Motif de la sortie...'
            }),
        }
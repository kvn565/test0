from django import forms
from .models import Societe

W = {'class': 'form-control'}
WS = {'class': 'form-select'}
WC = {'class': 'form-check-input'}


# ===================================================================
# Formulaire de mise à jour (utilisé dans le modal)
# ===================================================================
class SocieteUpdateForm(forms.ModelForm):
    """
    Formulaire utilisé dans le modal de modification
    """
    
    # Champs avec contraintes améliorées
    forme = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ex: SARL, SA, SAS, EI...'
        })
    )

    secteur = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ex: Commerce général, Import-export...'
        })
    )

    nom_complet_gerant = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    facture_pied_page = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 5,
            'placeholder': 'Mentions légales, RIB, conditions générales, etc.'
        })
    )

    class Meta:
        model = Societe
        fields = [
            'nom', 'nif', 'registre', 'boite_postal', 'telephone',
            'email_societe', 'logo', 'facture_logo', 'facture_pied_page',
            'province', 'commune', 'quartier', 'avenue', 'numero',
            'centre_fiscale',
            'assujeti_tva', 'assujeti_tc', 'assujeti_pfl',
            'secteur', 'forme', 'nom_complet_gerant', 'numero_depart',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Aucun champ obligatoire en modification
        for field in self.fields.values():
            field.required = False

        # Widgets par défaut
        for field_name, field in self.fields.items():
            if field_name in ['forme', 'secteur', 'nom_complet_gerant', 'facture_pied_page']:
                continue
            if isinstance(field.widget, forms.Select):
                field.widget.attrs.update(WS)
            elif isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update(WC)
            else:
                field.widget.attrs.update(W)


# ===================================================================
# Autres formulaires (obligatoires pour éviter l'ImportError)
# ===================================================================
class SocieteInscriptionChefForm(forms.ModelForm):
    class Meta:
        model = Societe
        fields = [
            'registre', 'boite_postal', 'telephone', 'email_societe', 'logo',
            'province', 'commune', 'quartier', 'avenue', 'numero',
            'centre_fiscale', 'assujeti_tva', 'assujeti_tc', 'assujeti_pfl',
            'secteur', 'forme', 'nom_complet_gerant',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = False


class SocieteForm(forms.ModelForm):
    class Meta:
        model = Societe
        fields = ['nom', 'nif']


class SocieteAdminConfigForm(forms.ModelForm):
    obr_password = forms.CharField(widget=forms.PasswordInput, required=False)

    class Meta:
        model = Societe
        fields = ['obr_username', 'obr_password', 'obr_system_id', 'obr_actif']
from django import forms
from .models import Societe

W = {'class': 'form-control'}
WS = {'class': 'form-select'}
WC = {'class': 'form-check-input'}


# ===================================================================
# 4. Formulaire principal de mise à jour (utilisé dans le modal)
# ===================================================================
class SocieteUpdateForm(forms.ModelForm):
    """
    Formulaire utilisé dans le modal de modification
    """
    class Meta:
        model = Societe
        fields = [
            'nom', 'nif', 'registre', 'boite_postal', 'telephone',
            'email_societe', 'logo', 
            'facture_logo',
            'facture_pied_page',      # ← Champ concerné
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

        # Widgets uniformes (ne touche à rien d'autre)
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs.update(WS)
            elif isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update(WC)
            else:
                field.widget.attrs.update(W)

        # ====================== CORRECTION UNIQUEMENT POUR PIED DE PAGE ======================
        self.fields['facture_pied_page'].widget = forms.Textarea(attrs={
            'class': 'form-control',      # Même classe que les autres champs
            'rows': 4,
            'style': 'width: 100%; max-width: 100%;',   # Même largeur que les autres
            'placeholder': 'Mentions légales, RIB, conditions de paiement, etc.'
        })


# ===================================================================
# Autres formulaires (laisser tels quels)
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


class SocieteForm(forms.ModelForm):
    class Meta:
        model = Societe
        fields = ['nom', 'nif']


class SocieteAdminConfigForm(forms.ModelForm):
    obr_password = forms.CharField(widget=forms.PasswordInput, required=False)

    class Meta:
        model = Societe
        fields = ['obr_username', 'obr_password', 'obr_system_id', 'obr_actif']
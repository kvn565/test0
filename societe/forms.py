# societe/forms.py — VERSION FINALE CORRIGÉE

from django import forms
from .models import Societe

W = {'class': 'form-control'}
WS = {'class': 'form-select'}
WC = {'class': 'form-check-input'}


# ===================================================================
# 1. Formulaire pour le CHEF lors de l'inscription (/setup/)
# ===================================================================
class SocieteInscriptionChefForm(forms.ModelForm):
    """
    Formulaire utilisé UNIQUEMENT par le chef lors de l'inscription.
    - Il ne peut PAS modifier 'nom' et 'nif' (fixés par le superadmin)
    - Il complète les informations manquantes de sa société
    """
    class Meta:
        model = Societe
        fields = [
            'registre',
            'boite_postal',
            'telephone',
            'email_societe',
            'logo',
            'province',
            'commune',
            'quartier',
            'avenue',
            'numero',
            'centre_fiscale',
            'assujeti_tva',
            'assujeti_tc',
            'assujeti_pfl',
            'secteur',
            'forme',
            'nom_complet_gerant',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Champs obligatoires pour le chef
        required_fields = ['registre', 'telephone', 'province', 'commune', 
                          'quartier', 'avenue', 'centre_fiscale', 'secteur', 'forme']
        for field in required_fields:
            if field in self.fields:
                self.fields[field].required = True

        # Champs facultatifs
        optional = ['boite_postal', 'numero', 'email_societe', 'nom_complet_gerant', 'logo']
        for field in optional:
            if field in self.fields:
                self.fields[field].required = False

        # Widgets uniformes
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs.update(WS)
            elif isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update(WC)
            else:
                field.widget.attrs.update(W)

        # Placeholders utiles
        self.fields['secteur'].widget.attrs['placeholder'] = 'Ex: Commerce, Services, Import/Export...'
        self.fields['forme'].widget.attrs['placeholder'] = 'Ex: SARL, SA, SPRL...'
        self.fields['nom_complet_gerant'].widget.attrs['placeholder'] = 'Ex: Jean Pierre Nkurikiye'

    # Gestion propre du logo
    logo = forms.ImageField(
        required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'}),
        label="Logo de la société",
        help_text="JPG ou PNG recommandé (max 2 Mo)"
    )


# ===================================================================
# 2. Formulaire pour le SUPERADMIN (création société)
# ===================================================================
class SocieteForm(forms.ModelForm):
    """Formulaire réservé au superadmin pour créer une nouvelle société"""
    class Meta:
        model = Societe
        fields = ['nom', 'nif']
        widgets = {
            'nom': forms.TextInput(attrs={**W, 'placeholder': 'Ex: SODECO SARL'}),
            'nif': forms.TextInput(attrs={**W, 'placeholder': 'Ex: 4000123456', 
                                         'style': 'font-family: monospace; font-weight: bold;'}),
        }


# ===================================================================
# 3. Formulaire pour config OBR (superadmin uniquement)
# ===================================================================
class SocieteAdminConfigForm(forms.ModelForm):
    obr_password = forms.CharField(
        widget=forms.PasswordInput(attrs={**W, 'placeholder': 'Mot de passe OBR'}),
        label="Mot de passe OBR",
        required=False,
        help_text="Laissez vide pour conserver le mot de passe actuel."
    )

    class Meta:
        model = Societe
        fields = ['obr_username', 'obr_password', 'obr_system_id', 'obr_actif']

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not self.cleaned_data.get('obr_password') and self.instance.pk:
            # Ne pas écraser le mot de passe existant
            instance.obr_password = Societe.objects.get(pk=self.instance.pk).obr_password
        if commit:
            instance.save()
        return instance


# ===================================================================
# 4. Formulaire pour gestion gérance (superadmin)
# ===================================================================
class SocieteGeranceForm(forms.ModelForm):
    class Meta:
        model = Societe
        fields = ['nom_complet_gerant', 'numero_depart', 'email_societe']
        widgets = {
            'nom_complet_gerant': forms.TextInput(attrs={**W}),
            'numero_depart': forms.NumberInput(attrs={**W}),
            'email_societe': forms.EmailInput(attrs={**W}),
        }

class SocieteUpdateForm(forms.ModelForm):
    class Meta:
        model = Societe
        fields = [
            'registre',
            'boite_postal',
            'telephone',
            'email_societe',
            'logo',
            'province',
            'commune',
            'quartier',
            'avenue',
            'numero',
            'centre_fiscale',
            'assujeti_tva',
            'assujeti_tc',
            'assujeti_pfl',
            'secteur',
            'forme',
            'nom_complet_gerant',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Aucun champ obligatoire (clé du problème)
        for field in self.fields.values():
            field.required = False
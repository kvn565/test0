from datetime import timedelta
from django import forms
from django.utils import timezone
from django.contrib.auth.forms import UserCreationForm

from .models import CleActivation, Utilisateur
from societe.models import Societe


# ═══════════════════════════════════════════════════════════════
#  SOCIÉTÉ — création par le superadmin
# ═══════════════════════════════════════════════════════════════
class SocieteForm(forms.ModelForm):
    class Meta:
        model = Societe
        fields = ['nom', 'nif']
        widgets = {
            'nom': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Ex: SODECO SARL',
                'autofocus': 'autofocus',
            }),
            'nif': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Ex: 4000123456',
                'style': 'font-family: monospace; font-weight: bold;',
            }),
        }
        labels = {
            'nom': 'Nom de la société',
            'nif': 'NIF (Numéro d\'Identification Fiscale)',
        }
        help_texts = {
            'nif': (
                'Le NIF doit être exact. Il servira de vérification lors de l\'inscription du chef. '
                'Le chef ne pourra pas s\'inscrire si ce NIF ne correspond pas.'
            ),
        }

    def clean_nif(self):
        nif = self.cleaned_data.get('nif', '').strip()
        if not self.instance.pk and Societe.objects.filter(nif=nif).exists():
            raise forms.ValidationError("Une société avec ce NIF existe déjà dans le système.")
        return nif


# ═══════════════════════════════════════════════════════════════
#  CLÉ D’ACTIVATION
# ═══════════════════════════════════════════════════════════════
class CleActivationForm(forms.ModelForm):
    class Meta:
        model = CleActivation
        fields = ['societe', 'type_plan', 'date_debut', 'date_fin', 'notes']
        widgets = {
            'societe': forms.Select(attrs={'class': 'form-control'}),
            'type_plan': forms.Select(attrs={'class': 'form-control', 'id': 'id_type_plan'}),
            'date_debut': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'date_fin': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'societe': 'Société (obligatoire)',
            'type_plan': 'Type de plan',
            'date_debut': 'Valide à partir du',
            'date_fin': "Valide jusqu'au (calculé automatiquement)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['societe'].required = True
        self.fields['date_debut'].required = False
        self.fields['date_fin'].required = False

    def clean(self):
        cleaned = super().clean()
        type_plan = cleaned.get('type_plan')
        date_debut = cleaned.get('date_debut')
        date_fin = cleaned.get('date_fin')

        if type_plan:
            maintenant = timezone.now()
            if not date_debut:
                date_debut = maintenant
                cleaned['date_debut'] = date_debut
            durees_jours = {'ESSAI': 14, 'STARTER': 182, 'BUSINESS': 365, 'ENTERPRISE': 730}
            if not date_fin:
                jours = durees_jours.get(type_plan, 182)
                date_fin = date_debut + timedelta(days=jours)
                cleaned['date_fin'] = date_fin

        if date_debut and date_fin and date_fin <= date_debut:
            raise forms.ValidationError("La date de fin doit être après la date de début.")

        return cleaned


# ═══════════════════════════════════════════════════════════════
#  RÉVOCATION DE CLÉ
# ═══════════════════════════════════════════════════════════════
class RevoquerCleForm(forms.Form):
    motif = forms.CharField(
        label="Raison de la révocation",
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': "Ex: Défaut de paiement, non-respect du contrat…"
        }),
        required=True,
    )


# ═══════════════════════════════════════════════════════════════
#  INSCRIPTION CHEF
# ═══════════════════════════════════════════════════════════════
class InscriptionChefForm(forms.Form):
    nif = forms.CharField(
        label="NIF (Numéro d'Identification Fiscale)",
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'autocomplete': 'off',
            'placeholder': 'Ex: 4000123456'
        }),
        help_text="Saisissez exactement le NIF fourni par l'administrateur système."
    )

    registre = forms.CharField(
        label="Registre de commerce", max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control'}), required=True
    )
    boite_postal = forms.CharField(
        label="Boîte postale", max_length=50, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    telephone = forms.CharField(
        label="Téléphone de la société", max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-control'}), required=True
    )
    email_societe = forms.EmailField(
        label="Email officiel de la société", required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )

    province = forms.CharField(label="Province", max_length=100,
                               widget=forms.TextInput(attrs={'class': 'form-control'}), required=True)
    commune = forms.CharField(label="Commune", max_length=100,
                              widget=forms.TextInput(attrs={'class': 'form-control'}), required=True)
    quartier = forms.CharField(label="Quartier", max_length=100,
                               widget=forms.TextInput(attrs={'class': 'form-control'}), required=True)
    avenue = forms.CharField(label="Avenue", max_length=150,
                             widget=forms.TextInput(attrs={'class': 'form-control'}), required=True)
    numero = forms.CharField(label="Numéro", max_length=20, required=False,
                             widget=forms.TextInput(attrs={'class': 'form-control'}))

    centre_fiscale = forms.ChoiceField(
        label="Centre fiscal",
        choices=Societe.CENTRE_FISCALE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=True
    )

    assujeti_tva = forms.BooleanField(label="Assujetti à la TVA", required=False,
                                      widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    assujeti_tc = forms.BooleanField(label="Assujetti à la Taxe de Consommation (TC)", required=False,
                                     widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    assujeti_pfl = forms.BooleanField(label="Assujetti au Prélèvement Forfaitaire Libératoire (PFL)", required=False,
                                      widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))

    forme = forms.CharField(label="Forme juridique", max_length=100,
                            widget=forms.TextInput(attrs={'class': 'form-control'}), required=True)
    secteur = forms.CharField(label="Secteur d'activité", max_length=250,
                              widget=forms.TextInput(attrs={'class': 'form-control'}), required=True)

    logo = forms.ImageField(label="Logo de la société", required=False,
                            widget=forms.ClearableFileInput(attrs={'class': 'form-control'}))

    nom_complet_gerant = forms.CharField(label="Nom complet du gérant", max_length=200, required=False,
                                         widget=forms.TextInput(attrs={'class': 'form-control'}))

    chef_nom = forms.CharField(label="Votre nom", max_length=100,
                               widget=forms.TextInput(attrs={'class': 'form-control'}), required=True)
    chef_postnom = forms.CharField(label="Votre post-nom", max_length=100,
                                   widget=forms.TextInput(attrs={'class': 'form-control'}), required=True)
    chef_prenom = forms.CharField(label="Votre prénom", max_length=100,
                                  widget=forms.TextInput(attrs={'class': 'form-control'}), required=True)
    chef_email = forms.EmailField(label="Votre email professionnel", required=False,
                                  widget=forms.EmailInput(attrs={'class': 'form-control'}))

    chef_username = forms.CharField(label="Nom d'utilisateur", max_length=150,
                                    widget=forms.TextInput(attrs={'class': 'form-control'}), required=True)
    chef_password1 = forms.CharField(label="Mot de passe", min_length=8,
                                     widget=forms.PasswordInput(attrs={'class': 'form-control'}), required=True)
    chef_password2 = forms.CharField(label="Confirmer le mot de passe",
                                     widget=forms.PasswordInput(attrs={'class': 'form-control'}), required=True)

    def clean_nif(self):
        nif = self.cleaned_data.get('nif', '').strip().upper()
        try:
            societe = Societe.objects.get(nif=nif)
        except Societe.DoesNotExist:
            raise forms.ValidationError("Ce NIF n'existe pas dans le système.")

        now = timezone.now()
        cle_active = societe.cles_activation.filter(
            statut='ACTIVE', date_debut__lte=now, date_fin__gte=now
        ).first()

        if not cle_active:
            raise forms.ValidationError("Aucune licence active pour ce NIF.")

        if Utilisateur.objects.filter(societe=societe, type_poste='DIRECTEUR').exists():
            raise forms.ValidationError("Un directeur est déjà inscrit pour cette société.")

        self._societe = societe
        self._cle_active = cle_active
        return nif

    def clean_chef_username(self):
        username = self.cleaned_data.get('chef_username', '').strip()
        if Utilisateur.objects.filter(username=username).exists():
            raise forms.ValidationError("Ce nom d'utilisateur est déjà pris.")
        return username

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('chef_password1') != cleaned.get('chef_password2'):
            self.add_error('chef_password2', "Les deux mots de passe ne correspondent pas.")

        cleaned['_societe'] = getattr(self, '_societe', None)
        cleaned['_cle_active'] = getattr(self, '_cle_active', None)
        return cleaned


# ═══════════════════════════════════════════════════════════════
#  CLÉ PAYANTE
# ═══════════════════════════════════════════════════════════════
class ClePayanteForm(forms.Form):
    cle_activation = forms.CharField(
        label="Clé de licence", max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Ex: SOD-4567-12M-AB3D4E',
            'style': 'font-family: monospace; font-weight: bold; text-transform: uppercase; letter-spacing: 2px;',
            'autocomplete': 'off', 'autofocus': 'autofocus',
        }),
    )

    def clean_cle_activation(self):
        return self.cleaned_data.get('cle_activation', '').strip().upper()


# ═══════════════════════════════════════════════════════════════
#  UTILISATEURS
# ═══════════════════════════════════════════════════════════════
class UtilisateurCreationForm(UserCreationForm):
    class Meta:
        model = Utilisateur
        fields = ['nom', 'postnom', 'prenom', 'username', 'email', 'type_poste', 'photo',
                  'droit_stock_categorie', 'droit_stock_produit', 'droit_stock_fournisseur',
                  'droit_stock_entree', 'droit_stock_sortie', 'droit_facture_pnb',
                  'droit_facture_fdnb', 'droit_facture_particulier', 'droit_devis',
                  'droit_rapports', 'is_superuser', 'actif']


class UtilisateurModificationForm(forms.ModelForm):
    class Meta:
        model = Utilisateur
        fields = ['nom', 'postnom', 'prenom', 'username', 'email', 'type_poste', 'photo',
                  'droit_stock_categorie', 'droit_stock_produit', 'droit_stock_fournisseur',
                  'droit_stock_entree', 'droit_stock_sortie', 'droit_facture_pnb',
                  'droit_facture_fdnb', 'droit_facture_particulier', 'droit_devis',
                  'droit_rapports', 'is_superuser', 'actif']


class ChangerMotDePasseForm(forms.Form):
    nouveau_mot_de_passe = forms.CharField(
        label="Nouveau mot de passe", min_length=8,
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    confirmer_mot_de_passe = forms.CharField(
        label="Confirmer le mot de passe",
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('nouveau_mot_de_passe') != cleaned.get('confirmer_mot_de_passe'):
            raise forms.ValidationError("Les deux mots de passe ne correspondent pas.")
        return cleaned


# ═══════════════════════════════════════════════════════════════
#  GESTION GÉRANCE
# ═══════════════════════════════════════════════════════════════
class SocieteGeranceForm(forms.ModelForm):
    class Meta:
        model = Societe
        fields = ['nom_complet_gerant', 'email_societe', 'numero_depart']
        widgets = {
            'nom_complet_gerant': forms.TextInput(attrs={'class': 'form-control'}),
            'email_societe': forms.EmailInput(attrs={'class': 'form-control'}),
            'numero_depart': forms.NumberInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'nom_complet_gerant': "Nom complet du gérant",
            'email_societe': "Email officiel de la société",
            'numero_depart': "Numéro de départ des factures",
        }


# ═══════════════════════════════════════════════════════════════
#  CONFIGURATION OBR (eBMS) — Avec obr_base_url
# ═══════════════════════════════════════════════════════════════
class SocieteAdminConfigForm(forms.ModelForm):
    obr_password = forms.CharField(
        label="Mot de passe OBR",
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Entrez le nouveau mot de passe OBR',
            'autocomplete': 'off'
        }),
        help_text="Laissez vide si vous ne souhaitez pas changer le mot de passe actuel."
    )

    class Meta:
        model = Societe
        fields = [
            'obr_actif',
            'obr_username',
            'obr_system_id',
            'obr_base_url',      # ← Champ ajouté (URL de l'API OBR)
        ]
        widgets = {
            'obr_actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'obr_username': forms.TextInput(attrs={'class': 'form-control'}),
            'obr_system_id': forms.TextInput(attrs={'class': 'form-control'}),
            'obr_base_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://ebms.obr.gov.bi:9443/ebms_api'
            }),
        }
        labels = {
            'obr_actif': "Activer l'intégration OBR (eBMS)",
            'obr_username': "Nom d'utilisateur OBR",
            'obr_system_id': "System ID OBR",
            'obr_base_url': "URL Base API OBR",
        }
        help_texts = {
            'obr_base_url': (
                'URL de base de l\'API OBR. Laissez ce champ vide pour utiliser '
                'l\'URL par défaut : https://ebms.obr.gov.bi:9443/ebms_api'
            ),
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        password = self.cleaned_data.get('obr_password')

        if not password and self.instance.pk:
            instance.obr_password = Societe.objects.get(pk=self.instance.pk).obr_password

        if commit:
            instance.save()
        return instance
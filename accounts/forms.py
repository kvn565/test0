# accounts/forms.py

from django import forms
from django.contrib.auth.password_validation import validate_password

from superadmin.models import Utilisateur


# ─────────────────────────────────────────────────────────────────
#  CONNEXION
# ─────────────────────────────────────────────────────────────────

class ConnexionForm(forms.Form):
    username = forms.CharField(
        label="Nom d'utilisateur",
        max_length=150,
        widget=forms.TextInput(attrs={
            'class':        'form-control',
            'placeholder':  "Votre nom d'utilisateur",
            'autofocus':    True,
            'autocomplete': 'username',
        }),
    )
    password = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(attrs={
            'class':        'form-control',
            'placeholder':  '••••••••',
            'autocomplete': 'current-password',
        }),
    )
    remember = forms.BooleanField(
        label="Se souvenir de moi",
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    # ==================== PROTECTION ANTI-ROBOT ====================
    not_a_robot = forms.BooleanField(
        label="Je ne suis pas un robot",
        required=True,
        error_messages={
            'required': "Vous devez confirmer que vous n'êtes pas un robot pour vous connecter."
        },
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    # ============================================================


# ─────────────────────────────────────────────────────────────────
#  PROFIL — Modification des infos personnelles
# ─────────────────────────────────────────────────────────────────

class ProfilForm(forms.ModelForm):
    """
    Permet à l'utilisateur de modifier son email et ses infos personnelles.
    N'expose pas le mot de passe — géré séparément par MotDePasseForm.
    """
    class Meta:
        model  = Utilisateur
        fields = ['prenom', 'nom', 'postnom', 'email']
        labels = {
            'prenom':  'Prénom',
            'nom':     'Nom',
            'postnom': 'Post-nom',
            'email':   'Email',
        }
        widgets = {
            'prenom':  forms.TextInput(attrs={'class': 'form-control'}),
            'nom':     forms.TextInput(attrs={'class': 'form-control'}),
            'postnom': forms.TextInput(attrs={'class': 'form-control'}),
            'email':   forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'votre@email.com'}),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        qs = Utilisateur.objects.filter(email=email).exclude(pk=self.instance.pk)
        if email and qs.exists():
            raise forms.ValidationError("Cet email est déjà utilisé par un autre compte.")
        return email


class MotDePasseForm(forms.Form):
    """
    Changement de mot de passe sécurisé.
    Vérifie l'ancien mot de passe avant d'accepter le nouveau.
    """
    ancien_password = forms.CharField(
        label="Mot de passe actuel",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '••••••••',
        }),
    )
    nouveau_password1 = forms.CharField(
        label="Nouveau mot de passe",
        min_length=6,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '••••••••',
        }),
        help_text="Minimum 6 caractères.",
    )
    nouveau_password2 = forms.CharField(
        label="Confirmer le nouveau mot de passe",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '••••••••',
        }),
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_ancien_password(self):
        ancien = self.cleaned_data.get('ancien_password')
        if not self.user.check_password(ancien):
            raise forms.ValidationError("Mot de passe actuel incorrect.")
        return ancien

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('nouveau_password1')
        p2 = cleaned.get('nouveau_password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError({'nouveau_password2': "Les mots de passe ne correspondent pas."})
        return cleaned

    def save(self):
        """Applique le nouveau mot de passe."""
        self.user.set_password(self.cleaned_data['nouveau_password1'])
        self.user.save(update_fields=['password'])
        return self.user
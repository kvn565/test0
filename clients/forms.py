from django import forms
from .models import Client, TypeClient


class TypeClientForm(forms.ModelForm):
    """
    Formulaire pour créer/modifier un type de client.
    La société est injectée depuis la vue.
    """
    class Meta:
        model = TypeClient
        fields = ['nom']
        labels = {
            'nom': 'Nom du type de client'
        }
        widgets = {
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex : Particulier, Société locale, Institution, ONG...',
                'autofocus': True,
            }),
        }

    def __init__(self, societe=None, *args, **kwargs):
        self.societe = societe
        super().__init__(*args, **kwargs)

    def clean_nom(self):
        nom = self.cleaned_data.get('nom', '').strip()
        if not nom:
            raise forms.ValidationError("Le nom du type est obligatoire.")

        if self.societe:
            qs = TypeClient.objects.filter(societe=self.societe, nom__iexact=nom)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("Un type de client avec ce nom existe déjà pour cette société.")
        
        return nom

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.societe and not obj.pk:
            obj.societe = self.societe
        if commit:
            obj.save()
        return obj


class ClientForm(forms.ModelForm):
    """
    Formulaire principal pour créer ou modifier un Client.
    """
    class Meta:
        model = Client
        fields = ['nom', 'nif', 'type_client', 'adresse', 'assujeti_tva']
        labels = {
            'nom': 'Nom / Raison sociale du client',
            'nif': 'NIF',
            'type_client': 'Type de client',
            'adresse': 'Adresse complète',
            'assujeti_tva': 'Assujetti à la TVA',
        }
        widgets = {
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex : Jean Dupont ou SODECO SA',
            }),
            'nif': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex : 1234567890',
            }),
            'adresse': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Ex : Avenue de l\'Indépendance, Quartier Rohero, Bujumbura',
            }),
            'type_client': forms.Select(attrs={
                'class': 'form-select'
            }),
            'assujeti_tva': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

    def __init__(self, societe=None, *args, **kwargs):
        self.societe = societe
        super().__init__(*args, **kwargs)

        # Rendre certains champs optionnels
        self.fields['nif'].required = False
        self.fields['adresse'].required = False
        self.fields['type_client'].required = False

        # Label vide pour le select
        self.fields['type_client'].empty_label = '-- Sélectionner un type de client --'

        # Filtrage critique : Afficher uniquement les types de la société courante
        if societe:
            queryset = TypeClient.objects.filter(societe=societe).order_by('nom')
            
            # Optionnel : Mettre en évidence le type par défaut
            default_type = queryset.filter(est_defaut=True).first()
            if default_type:
                # On peut personnaliser l'affichage du type par défaut dans la liste
                self.fields['type_client'].queryset = queryset
                # Astuce pour afficher "(Par défaut)" :
                self.fields['type_client'].label_from_instance = lambda obj: (
                    f"{obj.nom} (Par défaut)" if obj.est_defaut else obj.nom
                )
            else:
                self.fields['type_client'].queryset = queryset
        else:
            self.fields['type_client'].queryset = TypeClient.objects.none()

    def save(self, commit=True):
        obj = super().save(commit=False)
        
        # Assigner automatiquement la société lors de la création
        if self.societe and not obj.pk:
            obj.societe = self.societe

        if commit:
            obj.save()
        return obj
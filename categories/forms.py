# categories/forms.py

from django import forms
from .models import Categorie


class CategorieForm(forms.ModelForm):
    class Meta:
        model  = Categorie
        fields = ['nom', 'description']   # societe injecté dans la vue, pas dans le form
        widgets = {
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex : Informatique, Alimentation, Électronique...',
                'autofocus': True,
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description optionnelle de la catégorie...',
            }),
        }

    def __init__(self, societe=None, *args, **kwargs):
        self.societe = societe
        super().__init__(*args, **kwargs)

    def clean_nom(self):
        nom = self.cleaned_data.get('nom', '').strip()
        if self.societe:
            qs = Categorie.objects.filter(societe=self.societe, nom__iexact=nom)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("Une catégorie avec ce nom existe déjà.")
        return nom

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.societe and not obj.pk:
            obj.societe = self.societe
        if commit:
            obj.save()
        return obj

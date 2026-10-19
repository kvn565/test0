from django.db import models
from django.utils import timezone


class SyncProfile(models.Model):
    """Configuration de synchronisation COTE LOCAL (le client)."""
    societe = models.OneToOneField(
        'societe.Societe', on_delete=models.CASCADE, related_name='sync_profile'
    )
    remote_base_url = models.CharField(
        max_length=500, blank=True,
        help_text="URL de base de l'application en ligne (ex: https://app.exemple.bi)"
    )
    api_token = models.CharField(max_length=128, blank=True)
    enabled = models.BooleanField(default=False)
    numero_offset = models.PositiveIntegerField(
        default=0,
        help_text="Décalage de numérotation local pour éviter les doublons OBR (ex: 1_000_000)"
    )
    last_push_at = models.DateTimeField(null=True, blank=True)
    last_pull_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"SyncProfile({self.societe})"


class SyncToken(models.Model):
    """Jeton d'authentification COTE ONLINE (le serveur API)."""
    societe = models.OneToOneField(
        'societe.Societe', on_delete=models.CASCADE, related_name='sync_token'
    )
    token = models.CharField(max_length=128, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"SyncToken({self.societe})"


class SyncState(models.Model):
    """Watermark de synchronisation par modele et par sens."""
    societe = models.ForeignKey('societe.Societe', on_delete=models.CASCADE)
    model_name = models.CharField(max_length=80)
    last_push_at = models.DateTimeField(null=True, blank=True)
    last_pull_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [('societe', 'model_name')]

    def __str__(self):
        return f"SyncState({self.societe}, {self.model_name})"

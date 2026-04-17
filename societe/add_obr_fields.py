# societe/migrations/XXXX_add_obr_fields.py
# Remplacer XXXX par le numéro de migration suivant dans votre projet
# Commande : python manage.py makemigrations societe --name=add_obr_fields

from django.db import migrations, models


class Migration(migrations.Migration):

    # Remplacez '0001_initial' par votre dernière migration existante
    dependencies = [
        ('societe', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='societe',
            name='obr_username',
            field=models.CharField(
                blank=True, default='', max_length=100,
                verbose_name="Nom d'utilisateur OBR",
                help_text="Identifiant fourni par l'OBR pour l'accès à l'API eBMS.",
            ),
        ),
        migrations.AddField(
            model_name='societe',
            name='obr_password',
            field=models.CharField(
                blank=True, default='', max_length=100,
                verbose_name="Mot de passe OBR",
                help_text="Mot de passe fourni par l'OBR pour l'API eBMS.",
            ),
        ),
        migrations.AddField(
            model_name='societe',
            name='obr_system_id',
            field=models.CharField(
                blank=True, default='', max_length=100,
                verbose_name="Identifiant système OBR",
                help_text="Ex: ws440077324400027 — fourni par l'OBR avec le mot de passe.",
            ),
        ),
        migrations.AddField(
            model_name='societe',
            name='obr_actif',
            field=models.BooleanField(
                default=False,
                verbose_name="Intégration OBR activée",
                help_text="Activer l'envoi automatique des données à l'OBR.",
            ),
        ),
    ]

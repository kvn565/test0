from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('societe', '0014_clean_models_societe'),
    ]

    operations = [
        migrations.AddField(
            model_name='societe',
            name='smtp_email',
            field=models.EmailField(
                blank=True, default='', max_length=254,
                verbose_name='Email SMTP (expéditeur)',
                help_text='Adresse Gmail utilisée pour envoyer les emails (ex: votre.societe@gmail.com)'
            ),
        ),
        migrations.AddField(
            model_name='societe',
            name='smtp_password',
            field=models.CharField(
                blank=True, default='', max_length=255,
                verbose_name="Mot de passe d'application SMTP",
                help_text='Mot de passe d\'application Google (16 caractères) — généré depuis https://myaccount.google.com/apppasswords'
            ),
        ),
    ]

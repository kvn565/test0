from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devis', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='devis',
            name='uuid_public',
            field=models.CharField(blank=True, db_index=True, editable=False, max_length=64, verbose_name='UUID public'),
        ),
        migrations.AddField(
            model_name='devis',
            name='email_envoye',
            field=models.BooleanField(default=False, verbose_name='Email envoyé au client'),
        ),
        migrations.AddField(
            model_name='devis',
            name='date_envoi_email',
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
    ]

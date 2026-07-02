from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('facturer', '0018_alter_facture_total_ht_alter_facture_total_ttc_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='facture',
            name='obr_mode_envoye',
            field=models.BooleanField(default=False, editable=False, verbose_name='Envoyé en mode PRODUCTION'),
        ),
    ]

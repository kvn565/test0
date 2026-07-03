from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('produits', '0005_alter_produit_options_alter_produit_code_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='produit',
            name='obr_mode_envoye',
            field=models.BooleanField(default=False, editable=False, verbose_name='Mode PRODUCTION'),
        ),
    ]

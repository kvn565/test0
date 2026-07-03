from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('facturer', '0021_facture_obr_mode_envoye'),
        ('societe', '0012_societe_obr_mode_production'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='facture',
            unique_together={('societe', 'numero', 'obr_mode_envoye')},
        ),
    ]

from django.db import migrations
from decimal import Decimal


def set_obr_mode_on_existing(apps, schema_editor):
    TauxTVA = apps.get_model('taux', 'TauxTVA')
    for taux in TauxTVA.objects.select_related('societe').all():
        if taux.societe and taux.societe.obr_mode_production:
            taux.obr_mode_envoye = True
        else:
            taux.obr_mode_envoye = False
        taux.save(update_fields=['obr_mode_envoye'])


class Migration(migrations.Migration):

    dependencies = [
        ('taux', '0006_tauxtva_obr_mode_envoye'),
    ]

    operations = [
        migrations.RunPython(set_obr_mode_on_existing, reverse_code=migrations.RunPython.noop),
    ]

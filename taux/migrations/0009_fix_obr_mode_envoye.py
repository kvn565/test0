from django.db import migrations
from decimal import Decimal


def fix_obr_mode_on_default_rates(apps, schema_editor):
    TauxTVA = apps.get_model('taux', 'TauxTVA')
    valeurs_par_defaut = [Decimal("0.00"), Decimal("10.00"), Decimal("18.00")]
    for taux in TauxTVA.objects.select_related('societe').filter(valeur__in=valeurs_par_defaut):
        if taux.societe:
            expected = taux.societe.obr_mode_production
            if taux.obr_mode_envoye != expected:
                taux.obr_mode_envoye = expected
                taux.save(update_fields=['obr_mode_envoye'])


class Migration(migrations.Migration):

    dependencies = [
        ('taux', '0008_create_default_rates'),
    ]

    operations = [
        migrations.RunPython(fix_obr_mode_on_default_rates, reverse_code=migrations.RunPython.noop),
    ]

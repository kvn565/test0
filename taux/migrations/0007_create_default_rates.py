from django.db import migrations
from decimal import Decimal


def create_default_tva_rates(apps, schema_editor):
    Societe = apps.get_model('societe', 'Societe')
    TauxTVA = apps.get_model('taux', 'TauxTVA')

    created_count = 0
    for societe in Societe.objects.all():
        defaults = [
            {"nom": "TVA 0%",  "valeur": Decimal("0.00"), "est_defaut": False},
            {"nom": "TVA 10%", "valeur": Decimal("10.00"), "est_defaut": False},
            {"nom": "TVA 18%", "valeur": Decimal("18.00"), "est_defaut": False},
        ]

        for data in defaults:
            _, created = TauxTVA.objects.get_or_create(
                societe=societe,
                valeur=data["valeur"],
                defaults={
                    "nom": data["nom"],
                    "est_defaut": data["est_defaut"],
                    "obr_mode_envoye": societe.obr_mode_production,
                }
            )
            if created:
                created_count += 1

    if created_count:
        print(f"{created_count} taux TVA par defaut crees.")


class Migration(migrations.Migration):

    dependencies = [
        ('taux', '0006_tauxtva_obr_mode_envoye'),
    ]

    operations = [
        migrations.RunPython(create_default_tva_rates, reverse_code=migrations.RunPython.noop),
    ]

from django.db import migrations, models
from decimal import Decimal


def create_default_rates_test_mode(apps, schema_editor):
    Societe = apps.get_model('societe', 'Societe')
    TauxTVA = apps.get_model('taux', 'TauxTVA')

    noms_corrects = {
        Decimal("0.00"):  "TVA 0%",
        Decimal("10.00"): "TVA 10%",
        Decimal("18.00"): "TVA 18%",
    }

    valeurs = list(noms_corrects.keys())

    for societe in Societe.objects.all():
        for valeur in valeurs:
            taux, created = TauxTVA.objects.get_or_create(
                societe=societe,
                valeur=valeur,
                obr_mode_envoye=False,
                defaults={
                    "nom": noms_corrects[valeur],
                    "est_defaut": valeur == Decimal("18.00"),
                }
            )
            if not created and taux.nom != noms_corrects[valeur]:
                taux.nom = noms_corrects[valeur]
                taux.save(update_fields=['nom'])


class Migration(migrations.Migration):

    dependencies = [
        ('societe', '0013_alter_societe_obr_base_url'),
        ('taux', '0009_force_default_rates_production'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='tauxtva',
            name='unique_taux_valeur_par_societe',
        ),
        migrations.AlterUniqueTogether(
            name='tauxtva',
            unique_together={('societe', 'nom', 'obr_mode_envoye')},
        ),
        migrations.AddConstraint(
            model_name='tauxtva',
            constraint=models.UniqueConstraint(
                fields=('societe', 'valeur', 'obr_mode_envoye'),
                name='unique_taux_valeur_par_societe'
            ),
        ),
        migrations.RunPython(create_default_rates_test_mode, reverse_code=migrations.RunPython.noop),
    ]

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('facturer', '0019_devis_lignedevis'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='Devis'),
                migrations.DeleteModel(name='LigneDevis'),
            ],
            database_operations=[],
        ),
    ]

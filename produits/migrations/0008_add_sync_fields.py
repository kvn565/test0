from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('produits', '0007_alter_produit_options_alter_produit_unique_together_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='produit',
            name='sync_uuid',
            field=models.CharField(blank=True, editable=False, max_length=36, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='produit',
            name='sync_updated_at',
            field=models.DateTimeField(auto_now=True, blank=True, null=True),
        ),
    ]

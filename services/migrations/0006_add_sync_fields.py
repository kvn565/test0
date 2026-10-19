from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0005_alter_service_unique_together'),
    ]

    operations = [
        migrations.AddField(
            model_name='service',
            name='sync_uuid',
            field=models.CharField(blank=True, editable=False, max_length=36, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='service',
            name='sync_updated_at',
            field=models.DateTimeField(auto_now=True, blank=True, null=True),
        ),
    ]

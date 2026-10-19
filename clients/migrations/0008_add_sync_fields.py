from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0007_alter_client_unique_together_client_email_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='typeclient',
            name='sync_uuid',
            field=models.CharField(blank=True, editable=False, max_length=36, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='typeclient',
            name='sync_updated_at',
            field=models.DateTimeField(auto_now=True, blank=True, null=True),
        ),
        migrations.AddField(
            model_name='client',
            name='sync_uuid',
            field=models.CharField(blank=True, editable=False, max_length=36, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='client',
            name='sync_updated_at',
            field=models.DateTimeField(auto_now=True, blank=True, null=True),
        ),
    ]

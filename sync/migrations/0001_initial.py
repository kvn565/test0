from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('societe', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SyncProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('remote_base_url', models.CharField(blank=True, help_text="URL de base de l'application en ligne (ex: https://app.exemple.bi)", max_length=500)),
                ('api_token', models.CharField(blank=True, max_length=128)),
                ('enabled', models.BooleanField(default=False)),
                ('numero_offset', models.PositiveIntegerField(default=0, help_text="Décalage de numérotation local pour éviter les doublons OBR (ex: 1_000_000)")),
                ('last_push_at', models.DateTimeField(blank=True, null=True)),
                ('last_pull_at', models.DateTimeField(blank=True, null=True)),
                ('last_error', models.TextField(blank=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('societe', models.OneToOneField(on_delete=models.CASCADE, related_name='sync_profile', to='societe.Societe')),
            ],
        ),
        migrations.CreateModel(
            name='SyncToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.CharField(max_length=128, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('societe', models.OneToOneField(on_delete=models.CASCADE, related_name='sync_token', to='societe.Societe')),
            ],
        ),
        migrations.CreateModel(
            name='SyncState',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('model_name', models.CharField(max_length=80)),
                ('last_push_at', models.DateTimeField(blank=True, null=True)),
                ('last_pull_at', models.DateTimeField(blank=True, null=True)),
                ('societe', models.ForeignKey(on_delete=models.CASCADE, to='societe.Societe')),
            ],
            options={
                'unique_together': {('societe', 'model_name')},
            },
        ),
    ]

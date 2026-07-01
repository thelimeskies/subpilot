from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_environment_nomba_integration_mode"),
    ]

    operations = [
        migrations.AddField(
            model_name="environment",
            name="nomba_access_token_encrypted",
            field=models.CharField(blank=True, default="", max_length=1024),
        ),
        migrations.AddField(
            model_name="environment",
            name="nomba_credentials_validated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="environment",
            name="nomba_last_validation",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="environment",
            name="nomba_live_active",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="environment",
            name="nomba_refresh_token_encrypted",
            field=models.CharField(blank=True, default="", max_length=512),
        ),
        migrations.AddField(
            model_name="environment",
            name="nomba_sub_account_id",
            field=models.CharField(blank=True, default="", max_length=128),
        ),
        migrations.AddField(
            model_name="environment",
            name="nomba_token_expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

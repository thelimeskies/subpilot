from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_environment_publishable_key"),
    ]

    operations = [
        migrations.AddField(
            model_name="environment",
            name="nomba_integration_mode",
            field=models.CharField(
                choices=[
                    ("platform", "Platform-managed"),
                    ("byok", "Bring your own Nomba keys"),
                ],
                default="platform",
                max_length=16,
            ),
        ),
    ]

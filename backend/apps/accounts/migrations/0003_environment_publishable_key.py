from django.db import migrations, models


def populate_publishable_keys(apps, schema_editor):
    Environment = apps.get_model("accounts", "Environment")
    import secrets

    for environment in Environment.objects.all():
        if environment.publishable_key:
            continue
        mode = "live" if environment.mode == "live" else "test"
        environment.publishable_key = f"pk_{mode}_{secrets.token_urlsafe(24)}"
        environment.save(update_fields=["publishable_key"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_merchant_metadata"),
    ]

    operations = [
        migrations.AddField(
            model_name="environment",
            name="publishable_key",
            field=models.CharField(blank=True, db_index=True, default="", max_length=80),
        ),
        migrations.RunPython(populate_publishable_keys, migrations.RunPython.noop),
    ]

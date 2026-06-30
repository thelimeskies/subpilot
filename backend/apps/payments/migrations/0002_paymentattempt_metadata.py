"""S13: add ``PaymentAttempt.metadata`` for the ``routing_policy`` hint."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="paymentattempt",
            name="metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]

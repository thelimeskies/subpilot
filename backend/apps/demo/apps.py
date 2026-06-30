from django.apps import AppConfig


class DemoConfig(AppConfig):
    name = "apps.demo"
    label = "demo"
    default_auto_field = "django.db.models.BigAutoField"
    verbose_name = "Demo"

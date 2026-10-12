from django.apps import AppConfig


class PhotographConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "photograph"

    def ready(self) -> None:
        from photochart.imaging.pillow_config import configure_pillow_once

        configure_pillow_once()

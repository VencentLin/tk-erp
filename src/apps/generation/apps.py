from django.apps import AppConfig


class GenerationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.generation'
    verbose_name = 'AI生成引擎'

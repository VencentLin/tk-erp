from django.apps import AppConfig


class ExportAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.export_app'
    verbose_name = '产品导出'

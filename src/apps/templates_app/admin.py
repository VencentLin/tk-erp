from django.contrib import admin
from django.utils.html import format_html
from .models import TShirtTemplate
from apps.core.widgets import image_preview, AdminImagePreviewMixin


@admin.register(TShirtTemplate)
class TShirtTemplateAdmin(AdminImagePreviewMixin, admin.ModelAdmin):
    list_display = ['thumbnail', 'name', 'color', 'is_active', 'created_at']
    list_filter = ['color', 'is_active']
    search_fields = ['name']
    readonly_fields = ['created_at', 'preview_image']
    fields = ['name', 'image', 'preview_image', 'color', 'is_active', 'created_at']
    preview_fields = ['image']

    @admin.display(description='预览')
    def thumbnail(self, obj):
        return image_preview(obj)

    @admin.display(description='图片预览')
    def preview_image(self, obj):
        if obj.image and hasattr(obj.image, 'url'):
            return format_html(
                '<img src="{}" style="max-width:400px; border-radius:8px; border:1px solid #dee2e6;">',
                obj.image.url
            )
        return '暂无图片'

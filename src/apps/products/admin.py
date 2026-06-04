from django.contrib import admin
from django.utils.html import format_html
from .models import Product, GenerationLog
from apps.core.widgets import image_preview, AdminImagePreviewMixin


class GenerationLogInline(admin.TabularInline):
    model = GenerationLog
    readonly_fields = ['step', 'model_used', 'duration_ms', 'created_at']
    extra = 0
    can_delete = False


@admin.register(Product)
class ProductAdmin(AdminImagePreviewMixin, admin.ModelAdmin):
    list_display = ['thumbnail', 'id', 'title_preview', 'country', 'status', 'created_at']
    list_filter = ['country', 'status']
    search_fields = ['title', 'description']
    readonly_fields = ['created_at', 'updated_at', 'preview_print', 'preview_mockup']
    fieldsets = [
        ('基础信息', {'fields': ['country', 'pattern', 'template', 'status']}),
        ('生成图片', {'fields': ['print_image', 'preview_print', 'mockup_image', 'preview_mockup']}),
        ('商品信息', {'fields': ['title', 'description', 'size_info']}),
        ('其他', {'fields': ['error_message', 'created_at', 'updated_at']}),
    ]
    from apps.export_app.admin import export_as_zip, export_as_csv
    actions = [export_as_zip, export_as_csv]
    inlines = [GenerationLogInline]
    preview_fields = ['print_image', 'mockup_image']

    @admin.display(description='预览')
    def thumbnail(self, obj):
        return image_preview(obj, field_name='print_image') or image_preview(obj, field_name='mockup_image')

    @admin.display(description='标题')
    def title_preview(self, obj):
        return obj.title[:40] if obj.title else '-'

    @admin.display(description='印花预览')
    def preview_print(self, obj):
        if obj.print_image and hasattr(obj.print_image, 'url'):
            return format_html(
                '<img src="{}" style="max-width:400px; border-radius:8px; border:1px solid #dee2e6;">',
                obj.print_image.url
            )
        return '暂无图片'

    @admin.display(description='效果图预览')
    def preview_mockup(self, obj):
        if obj.mockup_image and hasattr(obj.mockup_image, 'url'):
            return format_html(
                '<img src="{}" style="max-width:400px; border-radius:8px; border:1px solid #dee2e6;">',
                obj.mockup_image.url
            )
        return '暂无图片'


@admin.register(GenerationLog)
class GenerationLogAdmin(admin.ModelAdmin):
    list_display = ['product', 'step', 'model_used', 'duration_ms', 'created_at']
    list_filter = ['step']
    readonly_fields = ['created_at']

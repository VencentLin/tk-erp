"""Admin 图片预览 Widget"""
from django.utils.html import format_html


def image_preview(obj, field_name='image', size=80):
    """列表中的缩略图预览"""
    img = getattr(obj, field_name, None)
    if img and hasattr(img, 'url'):
        return format_html(
            '<img src="{}" style="width:{}px; height:{}px; object-fit:cover; border-radius:4px; border:1px solid #dee2e6;">',
            img.url, size, size
        )
    return '-'


image_preview.short_description = '预览'


def image_preview_large(obj, field_name='image', size=200):
    """表单中的大图预览"""
    img = getattr(obj, field_name, None)
    if img and hasattr(img, 'url'):
        return format_html(
            '<img src="{}" style="max-width:{}px; max-height:{}px; border-radius:8px; border:1px solid #dee2e6; margin:10px 0;">',
            img.url, size, size
        )
    return format_html('<p style="color:#999;">暂无图片</p>')


class AdminImagePreviewMixin:
    """Admin 表单中显示当前图片预览"""

    def render_change_form(self, request, context, *args, **kwargs):
        obj = kwargs.get('obj')
        if obj:
            previews = {}
            for field in getattr(self, 'preview_fields', ['image']):
                img = getattr(obj, field, None)
                if img and hasattr(img, 'url'):
                    previews[field] = img.url
            context['image_previews'] = previews
        return super().render_change_form(request, context, *args, **kwargs)

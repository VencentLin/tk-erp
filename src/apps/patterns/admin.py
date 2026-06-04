from django.contrib import admin
from django.shortcuts import render, redirect
from django.urls import path
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.utils.html import format_html
from .models import Pattern
from .batch_import import batch_import_patterns
from apps.core.widgets import image_preview, AdminImagePreviewMixin


@admin.register(Pattern)
class PatternAdmin(AdminImagePreviewMixin, admin.ModelAdmin):
    list_display = ['thumbnail', 'id', 'source_type', 'note_preview', 'created_at']
    list_filter = ['source_type', 'is_deleted']
    search_fields = ['note']
    readonly_fields = ['created_at', 'image_hash', 'preview_image']
    fields = ['image', 'preview_image', 'source_type', 'note', 'image_hash', 'uploaded_by', 'created_at']
    change_list_template = 'admin/patterns/pattern_change_list.html'
    preview_fields = ['image']

    @admin.display(description='预览')
    def thumbnail(self, obj):
        return image_preview(obj)

    @admin.display(description='备注')
    def note_preview(self, obj):
        return obj.note[:60] if obj.note else '-'

    @admin.display(description='图片预览')
    def preview_image(self, obj):
        if obj.image and hasattr(obj.image, 'url'):
            return format_html(
                '<img src="{}" style="max-width:400px; border-radius:8px; border:1px solid #dee2e6;">',
                obj.image.url
            )
        return '暂无图片'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('batch-upload/', self.admin_site.admin_view(self.batch_upload_view),
                 name='patterns_batch_upload'),
        ]
        return custom_urls + urls

    def batch_upload_view(self, request):
        context = dict(
            self.admin_site.each_context(request),
            title='批量导入印花',
            results=None,
            error=None,
        )

        if request.method == 'POST':
            try:
                uploaded_files = request.FILES.getlist('images')
                excel_file = request.FILES.get('excel_file')

                if not uploaded_files and not excel_file:
                    messages.error(request, '请上传图片文件或 Excel 文件')
                    return HttpResponseRedirect(request.get_full_path())

                excel_data = None
                if excel_file and excel_file.size > 0:
                    excel_data = excel_file.read()

                import logging
                logger = logging.getLogger(__name__)
                logger.info(f'Batch import: {len(uploaded_files)} files, excel={excel_data is not None}')

                results = batch_import_patterns(
                    files=uploaded_files if uploaded_files else None,
                    excel_file=excel_data,
                    uploaded_by=request.user,
                )

                new_count = sum(1 for r in results if r.status == 'new')
                dup_count = sum(1 for r in results if r.status == 'duplicate')
                err_count = sum(1 for r in results if r.status == 'error')

                messages.success(
                    request,
                    f'导入完成: {new_count} 张新印花, {dup_count} 张重复跳过, {err_count} 张失败'
                )

                context['results'] = results
                context['new_count'] = new_count
                context['dup_count'] = dup_count
                context['err_count'] = err_count

            except Exception as e:
                import traceback
                logger = logging.getLogger(__name__)
                logger.exception('Batch import failed')
                context['error'] = f'{type(e).__name__}: {e}\n{traceback.format_exc()}'

        return render(request, 'admin/patterns/batch_upload.html', context)

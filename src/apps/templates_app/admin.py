from django.contrib import admin
from django.utils.html import format_html
from .models import TShirtTemplate


@admin.register(TShirtTemplate)
class TShirtTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'color', 'is_active', 'created_at']
    list_filter = ['color', 'is_active']
    search_fields = ['name', 'prompt_body']
    readonly_fields = ['created_at']
    fields = ['name', 'image', 'color', 'prompt_body', 'fabric', 'sizes', 'is_active', 'created_at']

from django.contrib import admin
from .models import TShirtTemplate


@admin.register(TShirtTemplate)
class TShirtTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'color', 'is_active', 'created_at']
    list_filter = ['color', 'is_active']
    search_fields = ['name']
    readonly_fields = ['created_at']

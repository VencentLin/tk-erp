from django.contrib import admin
from .models import PrintCategory


@admin.register(PrintCategory)
class PrintCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'is_active', 'created_at']
    search_fields = ['name', 'keywords', 'print_prompt']
    list_filter = ['is_active']

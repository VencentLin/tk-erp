from django.contrib import admin
from .models import Pattern


@admin.register(Pattern)
class PatternAdmin(admin.ModelAdmin):
    list_display = ['id', 'uploaded_by', 'source_type', 'is_deleted', 'created_at']
    list_filter = ['source_type', 'is_deleted']
    search_fields = ['note']
    readonly_fields = ['created_at']

from django.contrib import admin
from .models import Product, GenerationLog


class GenerationLogInline(admin.TabularInline):
    model = GenerationLog
    readonly_fields = ['step', 'model_used', 'duration_ms', 'created_at']
    extra = 0
    can_delete = False


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'country', 'status', 'created_at']
    list_filter = ['country', 'status']
    search_fields = ['title', 'description']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [GenerationLogInline]


@admin.register(GenerationLog)
class GenerationLogAdmin(admin.ModelAdmin):
    list_display = ['product', 'step', 'model_used', 'duration_ms', 'created_at']
    list_filter = ['step']
    readonly_fields = ['created_at']

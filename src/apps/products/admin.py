from django.contrib import admin
from .models import Product, ProductSKU


class ProductSKUInline(admin.TabularInline):
    model = ProductSKU
    readonly_fields = ['mockup_image']
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'country', 'category', 'status', 'created_at']
    list_filter = ['country', 'category', 'status']
    search_fields = ['title', 'description']
    inlines = [ProductSKUInline]


@admin.register(ProductSKU)
class ProductSKUAdmin(admin.ModelAdmin):
    list_display = ['id', 'product', 'template']

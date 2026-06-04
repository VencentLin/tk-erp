from django.contrib import admin
from .models import Country, Store


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ['code', 'name']
    search_fields = ['code', 'name']


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ['name', 'country', 'owner', 'is_active', 'created_at']
    list_filter = ['country', 'is_active']
    search_fields = ['name', 'owner__username']

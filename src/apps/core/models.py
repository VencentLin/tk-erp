from django.db import models
from django.conf import settings


class Country(models.Model):
    """国家（印尼/泰国/...）"""
    code = models.CharField(max_length=8, unique=True, help_text='ISO代码，如 ID, TH')
    name = models.CharField(max_length=64)

    class Meta:
        verbose_name = '国家'
        verbose_name_plural = '国家'
        ordering = ['code']

    def __str__(self):
        return self.name


class Store(models.Model):
    """TikTok Shop 店铺"""
    name = models.CharField(max_length=128)
    country = models.ForeignKey(
        Country, on_delete=models.PROTECT, related_name='stores'
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='stores'
    )
    api_credentials = models.JSONField(default=dict, blank=True, help_text='TikTok Shop API 凭证')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '店铺'
        verbose_name_plural = '店铺'
        ordering = ['country', 'name']

    def __str__(self):
        return self.name

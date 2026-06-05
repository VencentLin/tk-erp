from django.db import models
from apps.core.models import Country
from apps.templates_app.models import TShirtTemplate
from apps.categories.models import PrintCategory


class Product(models.Model):
    STATUS_CHOICES = [
        ('pending', '等待生成'), ('processing', '生成中'),
        ('completed', '已完成'), ('failed', '生成失败'),
        ('text_pending', '待补全文本'),
    ]
    country = models.ForeignKey(Country, on_delete=models.PROTECT, related_name='products')
    category = models.ForeignKey(PrintCategory, on_delete=models.PROTECT, related_name='products')
    template = models.ForeignKey(TShirtTemplate, on_delete=models.PROTECT, related_name='products')

    title = models.CharField(max_length=512, blank=True, default='')
    description = models.TextField(blank=True, default='')
    size_info = models.CharField(max_length=256, blank=True, default='')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    seed = models.IntegerField(default=0)
    background = models.CharField(max_length=256, blank=True, default='')
    error_message = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '生成产品'
        verbose_name_plural = '生成产品'
        ordering = ['-created_at']

    def __str__(self):
        return f'Product #{self.id} - {self.title[:50]}'


class ProductSKU(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='skus')
    template = models.ForeignKey(TShirtTemplate, on_delete=models.PROTECT)
    mockup_image = models.ImageField(upload_to='products/skus/%Y/%m/', blank=True, null=True)

    class Meta:
        verbose_name = '产品SKU'
        verbose_name_plural = '产品SKU'

    def __str__(self):
        return f'SKU #{self.id} - {self.template.color}'

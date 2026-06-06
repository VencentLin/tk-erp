from django.db import models
from apps.core.models import Country
from apps.templates_app.models import TShirtTemplate
from apps.categories.models import PrintCategory, PromptPreset


class Product(models.Model):
    STATUS_CHOICES = [
        ('pending', '等待生成'), ('processing', '生成中'),
        ('completed', '已完成'), ('failed', '生成失败'),
        ('text_pending', '待补全文本'),
    ]
    country = models.ForeignKey(Country, on_delete=models.PROTECT, related_name='products')
    category = models.ForeignKey(PrintCategory, on_delete=models.PROTECT, related_name='products', null=True, blank=True)
    template = models.ForeignKey(TShirtTemplate, on_delete=models.PROTECT, related_name='products', null=True, blank=True)
    prompt_preset = models.ForeignKey(PromptPreset, on_delete=models.PROTECT, related_name='products', null=True, blank=True, help_text='直接使用 .md 提示词预设')
    template_key = models.CharField(max_length=64, blank=True, default='', help_text='V6 产品模板 key，如 tshirt_white')
    generation_mode = models.CharField(max_length=16, choices=[('direct', 'AI 直出'), ('pod', 'POD 贴图')], default='direct')
    print_design = models.ForeignKey('categories.PrintDesign', on_delete=models.PROTECT, null=True, blank=True, related_name='products')

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
    template = models.ForeignKey(TShirtTemplate, on_delete=models.PROTECT, null=True, blank=True)
    mockup_image = models.ImageField(upload_to='products/skus/%Y/%m/', blank=True, null=True)

    class Meta:
        verbose_name = '产品SKU'
        verbose_name_plural = '产品SKU'

    def __str__(self):
        if self.template:
            return f'SKU #{self.id} - {self.template.color}'
        return f'SKU #{self.id}'

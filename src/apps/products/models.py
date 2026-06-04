from django.db import models
from apps.core.models import Country
from apps.patterns.models import Pattern
from apps.templates_app.models import TShirtTemplate
from .storage import ProductImageStorage


class Product(models.Model):
    """AI 生成的产品"""
    STATUS_CHOICES = [
        ('pending', '等待生成'),
        ('processing', '生成中'),
        ('completed', '已完成'),
        ('failed', '生成失败'),
        ('text_pending', '待补全文本'),
    ]

    country = models.ForeignKey(Country, on_delete=models.PROTECT, related_name='products')
    pattern = models.ForeignKey(Pattern, on_delete=models.PROTECT, related_name='products',
                                help_text='参考的原始印花')

    print_image = models.ImageField(upload_to='products/prints/%Y/%m/',
                                    storage=ProductImageStorage(), blank=True, null=True,
                                    help_text='生成的印花图（透明底）')

    title = models.CharField(max_length=512, blank=True, default='')
    description = models.TextField(blank=True, default='')
    size_info = models.CharField(max_length=256, blank=True, default='', help_text='尺码信息')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    error_message = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '生成产品'
        verbose_name_plural = '生成产品'
        ordering = ['-created_at']

    def __str__(self):
        return f'Product #{self.id} - {self.title[:50]}'

    @property
    def primary_sku(self):
        return self.skus.first()


class ProductSKU(models.Model):
    """产品 SKU — 不同颜色/模板的变体"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='skus')
    template = models.ForeignKey(TShirtTemplate, on_delete=models.PROTECT,
                                  help_text='使用的T恤模板')
    mockup_image = models.ImageField(upload_to='products/mockups/%Y/%m/',
                                      storage=ProductImageStorage(), blank=True, null=True,
                                      help_text='印花+T恤效果图')

    class Meta:
        verbose_name = '产品SKU'
        verbose_name_plural = '产品SKU'
        ordering = ['id']

    def __str__(self):
        return f'SKU #{self.id} - {self.template.name} ({self.template.color})'


class GenerationLog(models.Model):
    """AI 生成记录"""
    STEP_CHOICES = [
        ('preprocess', '预处理（抠图）'),
        ('image_gen', '印花生成'),
        ('text_gen', '文本生成'),
        ('write_storage', '存储写入'),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='generation_logs')
    step = models.CharField(max_length=20, choices=STEP_CHOICES)
    model_used = models.CharField(max_length=128, blank=True, default='')
    params = models.JSONField(default=dict, blank=True)
    duration_ms = models.PositiveIntegerField(default=0, help_text='耗时（毫秒）')
    token_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '生成记录'
        verbose_name_plural = '生成记录'
        ordering = ['product', 'created_at']

    def __str__(self):
        return f'{self.step} for Product #{self.product_id}'

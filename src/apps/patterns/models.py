from django.db import models
from django.conf import settings
from .storage import PatternImageStorage


class Pattern(models.Model):
    """原始印花图"""
    SOURCE_CHOICES = [
        ('clean_print', '干净印花（透明底）'),
        ('model_photo', '模特上身图'),
        ('product_photo', '产品平铺图'),
    ]

    image = models.ImageField(
        upload_to='patterns/%Y/%m/',
        storage=PatternImageStorage(),
        help_text='原始印花图片',
        blank=True,
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='patterns'
    )
    source_type = models.CharField(
        max_length=20, choices=SOURCE_CHOICES, default='clean_print',
        help_text='图片来源类型（决定是否需要抠图预处理）'
    )
    image_hash = models.CharField(max_length=64, blank=True, default='', db_index=True,
                                   help_text='图片 SHA256 哈希，用于查重')
    note = models.TextField(blank=True, default='')
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '原始印花'
        verbose_name_plural = '原始印花'
        ordering = ['-created_at']

    def __str__(self):
        return f'Pattern #{self.id}'

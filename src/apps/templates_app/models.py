from django.db import models
from .storage import TemplateImageStorage


class TShirtTemplate(models.Model):
    """T恤底图模板"""
    COLOR_CHOICES = [
        ('white', '白色'),
        ('black', '黑色'),
        ('gray', '灰色'),
        ('navy', '深蓝'),
        ('red', '红色'),
        ('other', '其他颜色'),
    ]

    name = models.CharField(max_length=128, help_text='模板名称，如"白色基础款圆领"')
    image = models.ImageField(
        upload_to='tshirt_templates/%Y/%m/',
        storage=TemplateImageStorage(),
        help_text='T恤底图（建议1024x1024以上PNG）',
        blank=True,  # Allow blank for testing without MinIO
    )
    color = models.CharField(max_length=16, choices=COLOR_CHOICES, default='white')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'T恤模板'
        verbose_name_plural = 'T恤模板'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.color})'

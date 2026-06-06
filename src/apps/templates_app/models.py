from django.db import models


class TShirtTemplate(models.Model):
    COLOR_CHOICES = [
        ('white', '白色'), ('black', '黑色'), ('gray', '灰色'),
        ('navy', '深蓝'), ('red', '红色'), ('other', '其他颜色'),
    ]
    name = models.CharField(max_length=128)
    image = models.ImageField(upload_to='templates/%Y/%m/', blank=True)
    color = models.CharField(max_length=16, choices=COLOR_CHOICES, default='white')
    prompt_body = models.TextField(blank=True, default='', help_text='豆包生成的版型提示词（含版型/颜色/领型/袖长）')
    fabric = models.CharField(max_length=256, blank=True, default='', help_text='面料描述，如 premium cotton, 230gsm')
    sizes = models.CharField(max_length=128, blank=True, default='XS,S,M,L,XL,XXL,3XL,4XL', help_text='可选尺码，逗号分隔')
    # POD 字段
    is_pod_template = models.BooleanField(default=False, help_text='可用于 POD 贴图模式')
    template_view = models.CharField(max_length=16, default='front', help_text='模板视图 (front only in v1)')
    print_area_x = models.IntegerField(null=True, blank=True, help_text='印花区域 X 坐标 (px)')
    print_area_y = models.IntegerField(null=True, blank=True, help_text='印花区域 Y 坐标 (px)')
    print_area_width = models.IntegerField(null=True, blank=True, help_text='印花区域宽度 (px)')
    print_area_height = models.IntegerField(null=True, blank=True, help_text='印花区域高度 (px)')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'T恤模板'
        verbose_name_plural = 'T恤模板'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.color})'

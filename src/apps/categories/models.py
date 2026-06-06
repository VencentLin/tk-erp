from django.db import models


class ImportTask(models.Model):
    """分类导入任务 — 追踪进度"""
    STATUS_CHOICES = [
        ('pending', '等待中'), ('processing', '执行中'),
        ('done', '已完成'), ('error', '失败'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    progress = models.TextField(blank=True, default='', help_text='当前步骤描述')
    result = models.JSONField(default=dict, blank=True, help_text='导入结果')
    error_message = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '导入任务'
        verbose_name_plural = '导入任务'


class PromptPreset(models.Model):
    """直接 .md 提示词预设 — 跳过豆包分析，直接用于生成"""
    SHIRT_COLOR_CHOICES = [
        ('white', '白色 T 恤'),
        ('black', '黑色 T 恤'),
        ('other', '其他'),
    ]
    name = models.CharField(max_length=256, unique=True, verbose_name='预设名')
    slug = models.SlugField(max_length=256, unique=True)
    content = models.TextField(help_text='完整正向 prompt 内容')
    negative_prompt = models.TextField(blank=True, default='', help_text='负面提示词')
    md_file = models.FileField(upload_to='prompts/', blank=True, help_text='原始 .md 文件')
    shirt_color = models.CharField(max_length=16, choices=SHIRT_COLOR_CHOICES, default='white', help_text='T 恤颜色分类')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '提示词预设'
        verbose_name_plural = '提示词预设'
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class PrintCategory(models.Model):
    name = models.CharField(max_length=128, unique=True, verbose_name='分类名')
    slug = models.SlugField(max_length=128, unique=True)
    keywords = models.TextField(blank=True, default='', help_text='匹配关键词，逗号分隔')
    print_prompt = models.TextField(blank=True, default='', help_text='印花设计描述（纯印花，不含服装）')
    style_context = models.TextField(blank=True, default='', help_text='场景/灯光/摄影风格（不含服装）')
    extra_prompt = models.TextField(blank=True, default='', help_text='额外提示词')
    negative_prompt = models.TextField(blank=True, default='',
        help_text='负面提示词')
    prompt_file = models.CharField(max_length=512, blank=True, default='', help_text='.md文件路径')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '印花分类'
        verbose_name_plural = '印花分类'
        ordering = ['name']

    def __str__(self):
        return self.name


class PrintDesignPreset(models.Model):
    """POD 印花提示词预设 — 只描述平面印花，不描述T恤/衣架/场景"""
    SHIRT_COLOR_CHOICES = [
        ('white', '白色 T 恤'),
        ('black', '黑色 T 恤'),
        ('other', '其他'),
    ]
    name = models.CharField(max_length=256, unique=True, verbose_name='预设名')
    slug = models.SlugField(max_length=256, unique=True)
    shirt_color = models.CharField(max_length=16, choices=SHIRT_COLOR_CHOICES, default='white', help_text='T 恤颜色分类')
    content = models.TextField(help_text='只描述平面印花图案，不描述T恤/衣架/场景')
    negative_prompt = models.TextField(blank=True, default='', help_text='负面提示词')
    variation_pool = models.JSONField(default=dict, blank=True, help_text='配色/构图/元素/质感随机池')
    md_file = models.FileField(upload_to='print_prompts/', blank=True, help_text='原始 .md 文件')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '印花提示词预设'
        verbose_name_plural = '印花提示词预设'
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class PrintDesign(models.Model):
    """POD 生成的单个印花设计"""
    preset = models.ForeignKey(PrintDesignPreset, on_delete=models.PROTECT, related_name='designs')
    shirt_color = models.CharField(max_length=16, choices=PrintDesignPreset.SHIRT_COLOR_CHOICES, default='white')
    prompt = models.TextField()
    negative_prompt = models.TextField(blank=True, default='')
    variation_metadata = models.JSONField(default=dict, blank=True)
    seed = models.IntegerField(default=0)
    raw_image = models.ImageField(upload_to='prints/raw/%Y/%m/', blank=True, null=True)
    transparent_image = models.ImageField(upload_to='prints/transparent/%Y/%m/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '印花设计'
        verbose_name_plural = '印花设计'
        ordering = ['-created_at']

    def __str__(self):
        return f'Print #{self.id} - {self.preset.name}'

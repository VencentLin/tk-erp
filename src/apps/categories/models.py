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

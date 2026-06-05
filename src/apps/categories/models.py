from django.db import models


class PrintCategory(models.Model):
    name = models.CharField(max_length=128, unique=True, verbose_name='分类名')
    slug = models.SlugField(max_length=128, unique=True)
    keywords = models.TextField(blank=True, default='', help_text='匹配关键词，逗号分隔')
    print_prompt = models.TextField(blank=True, default='', help_text='核心印花提示词')
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

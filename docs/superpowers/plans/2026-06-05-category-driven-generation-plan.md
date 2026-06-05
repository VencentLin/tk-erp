# TK-ERP V2 — 分类驱动产品生成 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development

**Goal:** 重构为分类驱动的 AI 产品生成 — 管理提示词分类代替管理原始图片，txt2img 一步生成带印花 T 恤实物图。

**Architecture:** 移除 Pattern 模型和抠图合成流程，新建 PrintCategory 分类系统，产品通过组合分类 prompt + 模板 prompt + 背景直接生成。

**Tech Stack:** Django + ComfyUI + 豆包 Vision + DeepSeek API

**设计文档:** `docs/superpowers/specs/2026-06-05-category-driven-generation-design.md`

---

## 迁移说明

本次重构将**删除**旧数据库，因为模型结构完全不同。开发环境测试数据直接丢弃。

---

### Task 1: 清理旧代码和数据库

- [ ] **Step 1: 删除旧数据库和迁移**
```bash
cd C:\Users\VincentLin\PycharmProjects\tk-erp\src
del db.sqlite3
del apps\core\migrations\0*.py
del apps\patterns\migrations\0*.py
del apps\products\migrations\0*.py
del apps\templates_app\migrations\0*.py
del apps\accounts\migrations\0*.py
```

- [ ] **Step 2: 删除不再需要的文件**
```bash
# 删除 Pattern 相关
rm -r apps/patterns/
rm -r patterns/
# 删除旧的 Prompts（V2 用分类 .md）
rm -r ai/prompts/
# 删除旧的 Celery 任务
rm -r celery_app/
rm -r ai/comfy_workflows/
```

- [ ] **Step 3: 更新 settings.py — 移除旧 app**
编辑 `src/config/settings/base.py`，从 INSTALLED_APPS 删除：
- `'apps.patterns'`
- `'apps.generation'` (保留但后面重建内容)

- [ ] **Step 4: 提交**
```bash
git add -A
git commit -m "refactor: remove Pattern model, old prompts, Celery tasks for V2"
```

---

### Task 2: 新建数据模型

**Files:**
- 修改: `src/apps/templates_app/models.py` — 加 prompt_body, fabric, fit_style
- 修改: `src/apps/products/models.py` — 重写 Product，新建 ProductSKU
- 新建: `src/apps/categories/models.py` — PrintCategory
- 新建: `src/apps/categories/admin.py`
- 更新: `src/config/settings/base.py` — 加 `apps.categories`

- [ ] **Step 1: 更新 TShirtTemplate 模型**

```python
# src/apps/templates_app/models.py
from django.db import models

class TShirtTemplate(models.Model):
    COLOR_CHOICES = [
        ('white', '白色'), ('black', '黑色'), ('gray', '灰色'),
        ('navy', '深蓝'), ('red', '红色'), ('other', '其他颜色'),
    ]
    name = models.CharField(max_length=128)
    image = models.ImageField(upload_to='templates/%Y/%m/', blank=True)
    color = models.CharField(max_length=16, choices=COLOR_CHOICES, default='white')
    prompt_body = models.TextField(blank=True, default='', help_text='豆包生成的版型提示词')
    fabric = models.CharField(max_length=256, blank=True, default='', help_text='面料描述，如 premium cotton, 230gsm')
    fit_style = models.CharField(max_length=64, blank=True, default='Oversized', help_text='版型')
    sizes = models.CharField(max_length=128, blank=True, default='XS,S,M,L,XL,XXL,3XL,4XL', help_text='可选尺码，逗号分隔')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'T恤模板'
        verbose_name_plural = 'T恤模板'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.color})'
```

- [ ] **Step 2: 新建 PrintCategory 模型**

```python
# src/apps/categories/models.py
from django.db import models

class PrintCategory(models.Model):
    name = models.CharField(max_length=128, unique=True)
    slug = models.SlugField(max_length=128, unique=True)
    keywords = models.TextField(blank=True, default='', help_text='匹配关键词，逗号分隔')
    print_prompt = models.TextField(blank=True, default='', help_text='核心印花提示词')
    extra_prompt = models.TextField(blank=True, default='', help_text='额外提示词')
    prompt_file = models.CharField(max_length=512, blank=True, default='', help_text='.md文件路径')
    negative_prompt = models.TextField(blank=True, default='', 
        help_text='负面提示词')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '印花分类'
        verbose_name_plural = '印花分类'
        ordering = ['name']

    def __str__(self):
        return self.name
```

- [ ] **Step 3: 重写 Product + 新建 ProductSKU**

```python
# src/apps/products/models.py
from django.db import models
from apps.core.models import Country
from apps.templates_app.models import TShirtTemplate
from apps.categories.models import PrintCategory

class Product(models.Model):
    STATUS_CHOICES = [
        ('pending', '等待生成'), ('processing', '生成中'),
        ('completed', '已完成'), ('failed', '生成失败'),
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
```

- [ ] **Step 4: 创建迁移并提交**
```bash
python manage.py makemigrations templates_app categories products core accounts
python manage.py migrate
python manage.py shell -c "from django.contrib.auth.models import User; u=User.objects.create_superuser('Admin',email='a@t.com',password='Admin123'); u.profile.role='admin'; u.profile.save()"
git add -A && git commit -m "feat: new data models for V2 - PrintCategory, simplified Product, ProductSKU"
```

---

### Task 3: 模板管理（升级版）

**Files:**
- 修改: `src/apps/dashboard/views.py` — 更新 template_upload/edit
- 修改: `src/apps/dashboard/templates/dashboard/template_upload.html`
- 修改: `src/apps/dashboard/templates/dashboard/template_edit.html`
- 修改: `src/apps/dashboard/templates/dashboard/template_list.html`

- [ ] **Step 1: 更新模板上传视图 — 加豆包分析**

```python
@staff_required
def template_upload(request):
    if request.method == 'POST':
        name = request.POST.get('name', '')
        color = request.POST.get('color', 'white')
        image = request.FILES.get('image')
        fabric = request.POST.get('fabric', '')
        fit_style = request.POST.get('fit_style', 'Oversized')
        sizes = request.POST.get('sizes', 'XS,S,M,L,XL,XXL,3XL,4XL')

        if image and name:
            # 豆包分析版型
            prompt_body = _analyze_template(image.read())
            tpl = TShirtTemplate.objects.create(
                name=name, color=color, image=image,
                prompt_body=prompt_body, fabric=fabric, fit_style=fit_style,
                sizes=sizes,
            )
            messages.success(request, '模板上传成功，已自动分析版型')
            return redirect('template_list')
    return render(request, 'dashboard/template_upload.html')
```

- [ ] **Step 2: 豆包分析版型函数**

```python
def _analyze_template(image_data: bytes) -> str:
    """豆包分析 T 恤模板，返回版型提示词"""
    import base64, requests
    from django.conf import settings

    img_b64 = base64.b64encode(image_data).decode()
    resp = requests.post(
        f'{settings.DEEPSEEK_BASE_URL}/chat/completions',
        headers={'Authorization': f'Bearer {settings.DEEPSEEK_API_KEY}', 'Content-Type': 'application/json'},
        json={
            'model': 'doubao-seed-2.0-lite',
            'messages': [{'role': 'user', 'content': [
                {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{img_b64}'}},
                {'type': 'text', 'text': (
                    'Describe this T-shirt in English as a concise prompt for AI image generation. '
                    'Include: color, fit style (oversized/regular/slim), neckline (round neck/V-neck), '
                    'sleeve length, and any visible details. Keep it under 30 words. '
                    'Example output: "oversized black t-shirt, drop shoulder, round neck, short sleeve"'
                )}
            ]}],
            'max_tokens': 100,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()['choices'][0]['message']['content'].strip()
```

- [ ] **Step 3: 更新模板编辑/列表页面**
  - 模板列表显示: 名称、颜色、版型、面料
  - 编辑页加: prompt_body、fabric、fit_style 输入框
  - 列表页加「重新分析」按钮（调豆包重新生成 prompt_body）

- [ ] **Step 4: 提交**

---

### Task 4: 分类管理系统

**Files:**
- 新建: `src/apps/dashboard/templates/dashboard/category_list.html`
- 新建: `src/apps/dashboard/templates/dashboard/category_edit.html`
- 修改: `src/apps/dashboard/views.py` — 分类 CRUD + 图集上传
- 修改: `src/apps/dashboard/urls.py` — 分类路由
- 新建: `src/apps/categories/prompts/` — 存放分类 .md 文件

- [ ] **Step 1: 分类列表页**
  - 显示所有分类，卡片式布局
  - 每个卡片: 分类名、印花提示词预览、关键词标签
  - 操作: 编辑、删除、查看 .md 内容

- [ ] **Step 2: 分类上传图集功能**

```python
@staff_required
def category_upload(request):
    if request.method == 'POST':
        files = request.FILES.getlist('images')
        if files:
            # 豆包分析图集
            categories = _analyze_image_collection(files)
            for cat_data in categories:
                # 检查是否已存在相似分类（关键词匹配）
                existing = PrintCategory.objects.filter(
                    Q(keywords__icontains=cat_data['keywords'][0]) |
                    Q(name__iexact=cat_data['name'])
                ).first()
                if existing:
                    # 更新现有分类
                    existing.keywords = ', '.join(set(
                        existing.keywords.split(', ') + cat_data['keywords']
                    ))
                    existing.print_prompt = _optimize_prompt(
                        existing.print_prompt, cat_data['print_prompt']
                    )
                    existing.save()
                    _update_category_md(existing)
                else:
                    cat = PrintCategory.objects.create(**cat_data)
                    _create_category_md(cat)
            messages.success(request, f'处理了 {len(categories)} 个分类')
            return redirect('category_list')
    return render(request, 'dashboard/category_upload.html')
```

- [ ] **Step 3: 豆包分析图集函数**

```python
def _analyze_image_collection(files) -> list[dict]:
    """豆包分析图集，返回分类列表"""
    import base64, requests, json as json_mod
    from django.conf import settings

    # 编码多张图（最多 10 张采样）
    images_b64 = []
    for f in files[:10]:
        f.seek(0)
        images_b64.append(base64.b64encode(f.read()).decode())

    content = []
    for img in images_b64:
        content.append({'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{img}'}})
    content.append({'type': 'text', 'text': (
        'Analyze these T-shirt print design images. Group them into distinct style categories '
        '(maximum 10 categories). For each category, provide in JSON format:\n'
        '[\n  {\n'
        '    "name": "Category Name (English)",\n'
        '    "keywords": ["keyword1", "keyword2", ...],\n'
        '    "print_prompt": "Detailed English prompt describing this print style for Stable Diffusion",\n'
        '    "extra_prompt": ""\n'
        '  },\n  ...\n]\n'
        'Focus on the PRINT DESIGN only (ignore the T-shirt/model). '
        'Keywords should be Chinese+English for matching. '
        'Print prompt should be detailed enough for SD to generate a similar new design.'
    )}])

    resp = requests.post(
        f'{settings.DEEPSEEK_BASE_URL}/chat/completions',
        headers={'Authorization': f'Bearer {settings.DEEPSEEK_API_KEY}', 'Content-Type': 'application/json'},
        json={'model': 'doubao-seed-2.0-lite', 'messages': [{'role': 'user', 'content': content}], 'max_tokens': 3000},
        timeout=60,
    )
    resp.raise_for_status()
    text = resp.json()['choices'][0]['message']['content'].strip()
    if text.startswith('```'): text = text.split('\n', 1)[1].rsplit('```', 1)[0]
    return json_mod.loads(text)
```

- [ ] **Step 4: 创建/更新 .md 文件**

```python
def _create_category_md(category):
    """根据分类创建 .md 提示词文件"""
    md_content = f"""# {category.name}

## 匹配关键词
{category.keywords}

## 印花 Prompt
{category.print_prompt}

## 完整生成 Prompt
{{template_prompt}}, {{fabric}}

[印花: {category.print_prompt}]

{{background}}, soft indoor lighting, commercial apparel photography,
front view, center composition, 85mm lens, ultra realistic, 8k

## 负面 Prompt
low quality, blurry, anime, cartoon, childish, cute style, plastic fabric,
polyester texture, oversaturated, bad anatomy, deformed clothing,
cropped garment, watermark, logo distortion, low resolution
"""
    filepath = CATEGORY_MD_DIR / f'{category.slug}.md'
    filepath.write_text(md_content, encoding='utf-8')
    category.prompt_file = str(filepath.relative_to(PROJECT_ROOT))
    category.save()
```

- [ ] **Step 5: 分类编辑页**
  - 编辑: name, keywords, print_prompt, extra_prompt, negative_prompt
  - 保存时自动更新 .md 文件
  - 预览 .md 内容

- [ ] **Step 6: 提交**

---

### Task 5: 产品生成（新流程）

**Files:**
- 修改: `src/apps/dashboard/views.py` — product_create, _run_generation
- 修改: `src/apps/dashboard/templates/dashboard/product_create.html`
- 修改: `src/apps/generation/comfyui.py` — 只用 txt2img

- [ ] **Step 1: 产品创建视图**

```python
@staff_required
def product_create(request):
    categories = PrintCategory.objects.filter(is_active=True)
    templates = TShirtTemplate.objects.filter(is_active=True)
    countries = Country.objects.all()

    if request.method == 'POST':
        category_id = request.POST.get('category')
        country_code = request.POST.get('country')
        template_ids = request.POST.getlist('templates')
        count = int(request.POST.get('count', 1))

        if not category_id or not country_code or not template_ids:
            messages.error(request, '请选择分类、国家和模板')
            return redirect('product_create')

        country = get_object_or_404(Country, code=country_code)
        category = get_object_or_404(PrintCategory, id=int(category_id))

        for i in range(count):
            # 随机选一个主模板
            main_tid = random.choice(template_ids)
            main_template = get_object_or_404(TShirtTemplate, id=int(main_tid))

            product = Product.objects.create(
                country=country, category=category, template=main_template,
                size_info=main_template.sizes,  # 自动带入模板尺码
                status='processing'
            )
            for tid in template_ids:
                tpl = get_object_or_404(TShirtTemplate, id=int(tid))
                ProductSKU.objects.create(product=product, template=tpl)

            threading.Thread(target=_run_generation_v2,
                             args=(product.id, i), daemon=True).start()

        messages.success(request, f'创建 {count} 个产品，正在生成...')
        return redirect('product_list')

    return render(request, 'dashboard/product_create.html', {
        'categories': categories, 'templates': templates, 'countries': countries,
    })
```

- [ ] **Step 2: V2 生成流水线**

```python
BACKGROUNDS = [
    'office chair background', 'wooden bookshelf background',
    'minimalist interior background', 'coffee shop background',
    'light gray clean background', 'cream white wall background',
    'modern room background', 'wood furniture background',
]

def _run_generation_v2(product_id, variant_index):
    """V2 生成: 组装 prompt → txt2img → 多SKU"""
    import time, random, io, json
    from PIL import Image
    from django.core.files.base import ContentFile

    product = Product.objects.select_related('category', 'template').get(id=product_id)
    skus = ProductSKU.objects.filter(product_id=product_id).select_related('template')
    category = product.category
    rng = random.Random(product_id * 1000 + variant_index)

    bg = rng.choice(BACKGROUNDS)
    product.background = bg
    product.seed = rng.randint(1, 999999999)
    product.save()

    # 生成主 SKU 图
    main_sku = skus.first()
    if main_sku:
        try:
            prompt = _build_product_prompt(main_sku.template, category, bg)
            seed = product.seed

            provider = ComfyUIProvider()
            result = provider.generate_image(prompt=prompt, params={
                'seed': seed, 'steps': 30, 'cfg_scale': 7.5,
                'width': 1024, 'height': 1024,
            })

            if result.images:
                img = result.images[0]
                buf = io.BytesIO()
                img.save(buf, format='JPEG', quality=92)
                buf.seek(0)
                main_sku.mockup_image.save(
                    f'product_{product_id}_sku_{main_sku.id}.jpg',
                    ContentFile(buf.getvalue()), save=True
                )
        except Exception as e:
            print(f'Main SKU gen failed: {e}')

    # 生成其他 SKU 图（同seed，只改颜色）
    for sku in skus[1:]:
        try:
            prompt = _build_product_prompt(sku.template, category, bg)
            provider = ComfyUIProvider()
            result = provider.generate_image(prompt=prompt, params={
                'seed': seed, 'steps': 30, 'cfg_scale': 7.5,
                'width': 1024, 'height': 1024,
            })
            if result.images:
                img = result.images[0]
                buf = io.BytesIO()
                img.save(buf, format='JPEG', quality=92)
                buf.seek(0)
                sku.mockup_image.save(
                    f'product_{product_id}_sku_{sku.id}.jpg',
                    ContentFile(buf.getvalue()), save=True
                )
        except Exception as e:
            print(f'SKU {sku.id} gen failed: {e}')

    # 文本生成
    try:
        _generate_text_v2(product_id)
    except Exception as e:
        product.status = 'text_pending'
        product.save()
        print(f'Text gen failed: {e}')
    else:
        product.status = 'completed'
        product.save()


def _build_product_prompt(template, category, background):
    """组装完整产品 prompt"""
    return (
        f"{template.prompt_body}, {template.fabric}, "
        f"{category.print_prompt} graphic print centered on chest, "
        f"{background}, soft indoor lighting, commercial apparel photography, "
        f"front view, center composition, 85mm lens, ultra realistic, 8k"
    )
```

- [ ] **Step 3: 更新产品创建页面**
  - 分类选择: 卡片式，每个分类显示印花 prompt 预览
  - 模板选择: 复选框（多选=多SKU）
  - 数量选择: 数字输入（1-20）
  - 国家选择: 单选

- [ ] **Step 4: 提交**

---

### Task 6: 产品库 + 导出（适配新模型）

**Files:**
- 修改: `src/apps/dashboard/views.py` — product_list, product_edit, product_delete
- 修改: `src/apps/dashboard/templates/dashboard/product_list.html`
- 修改: `src/apps/dashboard/templates/dashboard/product_edit.html`
- 修改: `src/apps/export_app/services.py`

- [ ] **Step 1: 产品列表** — 显示分类名、模板色、SKU预览、状态
- [ ] **Step 2: 产品编辑** — 编辑标题描述、查看SKU图
- [ ] **Step 3: 导出** — 适配新的 Product + SKU 结构
- [ ] **Step 4: 提交**

---

### Task 7: 清理 integration + 最终提交

- [ ] **Step 1: 更新侧边栏** — 加「分类管理」，移除「印花管理」
- [ ] **Step 2: 更新设置页** — 移除旧变体设置
- [ ] **Step 3: 整理代码** — 清理 views.py 中的旧函数
- [ ] **Step 4: 更新 README**
- [ ] **Step 5: 提交并推送**

---

## 实现顺序

```
Task 1 (清理) → Task 2 (新模型) → Task 3 (模板升级)
                                 → Task 4 (分类系统)
                                 → Task 5 (产品生成)
                                 → Task 6 (产品库)
                                 → Task 7 (收尾)
```

Task 3 和 Task 4 可以并行。

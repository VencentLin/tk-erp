"""运营面板视图 — V2 分类驱动生成"""
import json, io, threading, sys, os, random, time
os.environ.setdefault('ORT_PROVIDERS', 'CPUExecutionProvider')

from pathlib import Path
from PIL import Image
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import HttpResponse
from django.contrib.auth.models import User
from django.db.models import Q
from django.conf import settings
from django.core.files.base import ContentFile

from apps.templates_app.models import TShirtTemplate
from apps.products.models import Product, ProductSKU
from apps.core.models import Country, Store
from apps.categories.models import PrintCategory

staff_required = user_passes_test(lambda u: u.is_staff, login_url='/admin/login/')
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CATEGORY_MD_DIR = Path(__file__).resolve().parent.parent / 'categories' / 'prompts'

BACKGROUNDS = [
    'office chair background', 'wooden bookshelf background',
    'minimalist interior background', 'coffee shop background',
    'light gray clean background', 'cream white wall background',
    'modern room background', 'wood furniture background',
]

# ============================================================
# Settings
# ============================================================

@staff_required
def settings_page(request):
    from apps.generation.comfyui import ComfyUIProvider
    provider = ComfyUIProvider()
    models = provider.get_available_checkpoints()
    current_model = provider.model
    config_path = PROJECT_ROOT / 'data' / 'config.json'

    if request.method == 'POST':
        selected_model = request.POST.get('model', current_model)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w') as f:
            json.dump({'comfyui_model': selected_model}, f)
        messages.success(request, f'已切换模型: {selected_model}')
        return redirect('settings_page')

    return render(request, 'dashboard/settings.html', {'models': models, 'current_model': current_model})

# ============================================================
# Dashboard
# ============================================================
@staff_required
def index(request):
    ctx = {
        'category_count': PrintCategory.objects.filter(is_active=True).count(),
        'template_count': TShirtTemplate.objects.filter(is_active=True).count(),
        'product_count': Product.objects.count(),
        'completed_count': Product.objects.filter(status='completed').count(),
        'recent_products': Product.objects.prefetch_related('skus').select_related('category', 'country').order_by('-created_at')[:8],
        'countries': Country.objects.all(),
    }
    return render(request, 'dashboard/index.html', ctx)

# ============================================================
# Country & Store (unchanged from V1)
# ============================================================
@staff_required
def country_list(request):
    return render(request, 'dashboard/country_list.html', {
        'countries': Country.objects.all(),
        'stores': Store.objects.select_related('country', 'owner').all()
    })

@staff_required
def country_save(request):
    if request.method == 'POST':
        cid = request.POST.get('id')
        code = request.POST.get('code', '').strip().upper()
        name = request.POST.get('name', '').strip()
        if code and name:
            if cid: c = get_object_or_404(Country, id=int(cid)); c.code, c.name = code, name; c.save()
            else: Country.objects.create(code=code, name=name)
    return redirect('country_list')

@staff_required
def country_delete(request, cid): Country.objects.filter(id=cid).delete(); return redirect('country_list')

@staff_required
def store_save(request):
    if request.method == 'POST':
        sid = request.POST.get('id')
        country = get_object_or_404(Country, id=int(request.POST['country_id']))
        name = request.POST.get('name', '').strip()
        if name:
            if sid: s = get_object_or_404(Store, id=int(sid)); s.name, s.country, s.owner = name, country, request.user; s.save()
            else: Store.objects.create(name=name, country=country, owner=request.user)
    return redirect('country_list')

@staff_required
def store_delete(request, sid): Store.objects.filter(id=sid).delete(); return redirect('country_list')

# ============================================================
# User Management
# ============================================================
@staff_required
def user_list(request):
    return render(request, 'dashboard/user_list.html', {'users': User.objects.select_related('profile').all()})

@staff_required
def user_save(request):
    if request.method == 'POST':
        uid = request.POST.get('id')
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        role = request.POST.get('role', 'operator')
        if uid:
            u = get_object_or_404(User, id=int(uid)); u.username = username
            if password: u.set_password(password)
            u.profile.role = role; u.profile.save(); u.save()
        elif username and password:
            u = User.objects.create_user(username=username, password=password)
            u.profile.role = role; u.profile.save()
    return redirect('user_list')

@staff_required
def user_delete(request, uid):
    if request.user.id != int(uid): User.objects.filter(id=uid).delete()
    return redirect('user_list')

# ============================================================
# Template Management (V2 upgrade - Doubao analysis + manual input)
# ============================================================
@staff_required
def template_list(request):
    return render(request, 'dashboard/template_list.html', {
        'templates': TShirtTemplate.objects.filter(is_active=True).order_by('-created_at')
    })

@staff_required
def template_upload(request):
    if request.method == 'POST':
        name = request.POST.get('name', '')
        color = request.POST.get('color', 'white')
        image = request.FILES.get('image')
        fabric = request.POST.get('fabric', '')
        sizes = request.POST.get('sizes', 'XS,S,M,L,XL,XXL,3XL,4XL')
        if image and name:
            prompt_body = _analyze_template(image.read())
            TShirtTemplate.objects.create(name=name, color=color, image=image,
                                          prompt_body=prompt_body, fabric=fabric, sizes=sizes)
            messages.success(request, '模板上传成功，已自动分析版型')
            return redirect('template_list')
    return render(request, 'dashboard/template_upload.html')

@staff_required
def template_edit(request, tid):
    t = get_object_or_404(TShirtTemplate, id=tid)
    if request.method == 'POST':
        t.name = request.POST.get('name', t.name)
        t.color = request.POST.get('color', t.color)
        t.fabric = request.POST.get('fabric', t.fabric)
        t.prompt_body = request.POST.get('prompt_body', t.prompt_body)
        t.sizes = request.POST.get('sizes', t.sizes)
        if request.FILES.get('image'):
            t.image = request.FILES['image']
            t.prompt_body = _analyze_template(request.FILES['image'].read())
        t.is_active = request.POST.get('is_active') == 'on'
        t.save()
        messages.success(request, '已更新')
        return redirect('template_list')
    return render(request, 'dashboard/template_edit.html', {'template': t})

@staff_required
def template_delete(request, tid):
    t = get_object_or_404(TShirtTemplate, id=tid); t.is_active = False; t.save()
    return redirect('template_list')

def _analyze_template(image_data: bytes) -> str:
    """豆包分析 T 恤模板，返回版型提示词"""
    import base64, requests, json as json_mod
    img_b64 = base64.b64encode(image_data).decode()
    resp = requests.post(
        f'{settings.DEEPSEEK_BASE_URL}/chat/completions',
        headers={'Authorization': f'Bearer {settings.DEEPSEEK_API_KEY}', 'Content-Type': 'application/json'},
        json={'model': 'doubao-seed-2.0-lite', 'messages': [{'role': 'user', 'content': [
            {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{img_b64}'}},
            {'type': 'text', 'text': (
                'Describe ONLY the physical attributes of this T-shirt in a few words (under 20 words). '
                'Include: exact color name, fit style (oversized/regular/slim), neckline type, sleeve length. '
                'CRITICAL: Do NOT use words like "plain", "blank", "solid", "empty", "isolated", or "background". '
                'Do NOT describe the photo setup or background. '
                'Example good output: "black oversized t-shirt, round neck, short sleeve"'
            )}
        ]}], 'max_tokens': 100}, timeout=60)
    resp.raise_for_status()
    return resp.json()['choices'][0]['message']['content'].strip()

# ============================================================
# Category Management (NEW)
# ============================================================
@staff_required
def category_list(request):
    return render(request, 'dashboard/category_list.html', {
        'categories': PrintCategory.objects.all().order_by('name')
    })

@staff_required
def category_upload(request):
    """上传图集 → 后台去重 → 豆包分析 → 创建/更新分类"""
    if request.method == 'POST':
        files = request.FILES.getlist('images')
        excel_file = request.FILES.get('excel_file')

        if not files and not excel_file:
            messages.error(request, '请上传图片或 Excel 文件')
            return redirect('category_upload')

        # 保存文件数据到内存（因为后台线程不能访问 request.FILES）
        files_data = []
        for f in files:
            if f.size > 0:
                files_data.append({'name': f.name, 'data': f.read()})
        excel_data = excel_file.read() if (excel_file and excel_file.size > 0) else None

        # 创建任务
        from apps.categories.models import ImportTask
        task = ImportTask.objects.create(status='pending', progress='准备分析...')
        task.progress = '任务已创建，等待执行...'
        task.save()

        # 后台执行
        threading.Thread(target=_run_category_import, args=(task.id, files_data, excel_data, request.user.username),
                         daemon=True).start()

        return redirect('category_task_status', task_id=task.id)

    return render(request, 'dashboard/category_upload.html', {})


def _run_category_import(task_id, files_data, excel_data, username):
    """后台执行分类导入"""
    from apps.categories.models import ImportTask
    task = ImportTask.objects.get(id=task_id)
    task.status = 'processing'
    task.progress = 'Step 1/4: 收集图片...'
    task.save()

    try:
        # Step 1: 构建文件对象列表用于去重
        from django.core.files.uploadedfile import SimpleUploadedFile
        uploaded_files = []
        for fd in files_data:
            uploaded_files.append(SimpleUploadedFile(fd['name'], fd['data']))

        # Step 2: 去重
        from apps.categories.batch_import import batch_collect_images
        task.progress = 'Step 2/4: 查重过滤中...'
        task.save()
        results, unique_images = batch_collect_images(
            files=uploaded_files if uploaded_files else None,
            excel_file=excel_data,
        )

        ok_count = sum(1 for r in results if r.status == 'ok')
        dup_count = sum(1 for r in results if r.status == 'duplicate')
        err_count = sum(1 for r in results if r.status == 'error')

        task.result = {'collected': ok_count, 'duplicates': dup_count, 'errors': err_count,
                       'created': 0, 'updated': 0}
        task.progress = f'Step 3/4: 收集 {ok_count} 张，去重 {dup_count} 张，豆包分析中...'
        task.save()

        if unique_images:
            # Step 3: 豆包分析分类
            categories = _analyze_image_collection(unique_images)
            task.progress = 'Step 3/4: 豆包已识别分类，创建中...'
            task.save()

            created_count, updated_count = 0, 0
            for cat_data in categories:
                slug = cat_data['name'].lower().replace(' ', '-').replace('/', '-')
                existing = PrintCategory.objects.filter(
                    Q(name__iexact=cat_data['name']) | Q(slug=slug)
                ).first()
                if existing:
                    existing.keywords = ', '.join(set(existing.keywords.split(', ') + cat_data['keywords']))
                    existing.print_prompt = cat_data['print_prompt']
                    existing.extra_prompt = cat_data.get('extra_prompt', '')
                    existing.save()
                    _update_category_md(existing)
                    updated_count += 1
                else:
                    PrintCategory.objects.create(
                        name=cat_data['name'], slug=slug,
                        keywords=', '.join(cat_data['keywords']),
                        print_prompt=cat_data['print_prompt'],
                        extra_prompt=cat_data.get('extra_prompt', ''),
                    )
                    # .md file
                    cat = PrintCategory.objects.get(slug=slug)
                    _create_category_md(cat)
                    created_count += 1

            task.result = {'collected': ok_count, 'duplicates': dup_count, 'errors': err_count,
                           'created': created_count, 'updated': updated_count}
            task.progress = f'Step 4/4: 完成！{created_count} 新分类 + {updated_count} 更新'
        else:
            task.progress = f'完成：无新图片（去重 {dup_count} 张）'

        task.status = 'done'
        task.save()

    except Exception as e:
        import traceback
        task.status = 'error'
        task.error_message = f'{type(e).__name__}: {e}\n{traceback.format_exc()}'
        task.progress = '执行失败'
        task.save()


@staff_required
def category_task_status(request, task_id):
    """查看导入任务进度"""
    from apps.categories.models import ImportTask
    task = get_object_or_404(ImportTask, id=task_id)
    return render(request, 'dashboard/category_task_status.html', {'task': task})

@staff_required
def category_edit(request, cid):
    cat = get_object_or_404(PrintCategory, id=cid)
    if request.method == 'POST':
        cat.name = request.POST.get('name', cat.name)
        cat.keywords = request.POST.get('keywords', cat.keywords)
        cat.print_prompt = request.POST.get('print_prompt', cat.print_prompt)
        cat.extra_prompt = request.POST.get('extra_prompt', cat.extra_prompt)
        cat.negative_prompt = request.POST.get('negative_prompt', cat.negative_prompt)
        cat.is_active = request.POST.get('is_active') == 'on'
        cat.save()
        _update_category_md(cat)
        messages.success(request, '分类已更新')
        return redirect('category_list')
    # Read .md content for preview
    md_content = ''
    if cat.prompt_file:
        md_path = PROJECT_ROOT / cat.prompt_file
        if md_path.exists():
            md_content = md_path.read_text(encoding='utf-8')
    return render(request, 'dashboard/category_edit.html', {'category': cat, 'md_content': md_content})

@staff_required
def category_delete(request, cid):
    cat = get_object_or_404(PrintCategory, id=cid)
    cat.is_active = False; cat.save()
    return redirect('category_list')

def _analyze_image_collection(files) -> list:
    """豆包分析图集（接受 bytes 列表或 Django UploadedFile 列表），返回分类列表"""
    import base64, requests, json as json_mod
    # 最多采样 5 张图避免超时和 token 超限
    images_b64 = []
    for f in files[:5]:
        if isinstance(f, bytes):
            images_b64.append(base64.b64encode(f).decode())
        else:
            f.seek(0)
            images_b64.append(base64.b64encode(f.read()).decode())

    content = []
    for img in images_b64:
        content.append({'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{img}'}})
    content.append({'type': 'text', 'text': (
        'Analyze these T-shirt print design images. Group them into distinct style categories (max 10). '
        'For each category, return a JSON array:\n'
        '[{"name": "Category Name", "keywords": ["kw1","kw2",...], '
        '"print_prompt": "Detailed SD prompt for this print style", "extra_prompt": ""}]\n'
        'Focus on PRINT DESIGN only. Keywords in Chinese+English. Print prompt detailed enough for SD.'
    )})

    resp = requests.post(
        f'{settings.DEEPSEEK_BASE_URL}/chat/completions',
        headers={'Authorization': f'Bearer {settings.DEEPSEEK_API_KEY}', 'Content-Type': 'application/json'},
        json={'model': 'doubao-seed-2.0-lite', 'messages': [{'role': 'user', 'content': content}], 'max_tokens': 3000},
        timeout=180)  # 3 分钟超时
    resp.raise_for_status()
    text = resp.json()['choices'][0]['message']['content'].strip()
    if text.startswith('```'): text = text.split('\n', 1)[1].rsplit('```', 1)[0]
    return json_mod.loads(text)

def _create_category_md(category):
    """创建分类 .md 文件"""
    md = f"""# {category.name}

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
    CATEGORY_MD_DIR.mkdir(parents=True, exist_ok=True)
    filepath = CATEGORY_MD_DIR / f'{category.slug}.md'
    filepath.write_text(md, encoding='utf-8')
    category.prompt_file = str(filepath.relative_to(PROJECT_ROOT))
    category.negative_prompt = 'low quality, blurry, anime, cartoon, childish, cute style, plastic fabric, polyester texture, oversaturated, bad anatomy, deformed clothing, cropped garment, watermark, logo distortion, low resolution'
    category.save()

def _update_category_md(category):
    """更新分类 .md 文件"""
    if category.prompt_file:
        _create_category_md(category)

# ============================================================
# Product Management (V2 - category-driven)
# ============================================================
@staff_required
def product_list(request):
    country_code = request.GET.get('country', '')
    status = request.GET.get('status', '')
    products = Product.objects.prefetch_related('skus__template').select_related('country', 'category').order_by('-created_at')
    if country_code: products = products.filter(country__code=country_code)
    if status: products = products.filter(status=status)
    return render(request, 'dashboard/product_list.html', {
        'products': products, 'countries': Country.objects.all(),
        'statuses': Product.STATUS_CHOICES,
        'selected_country': country_code, 'selected_status': status,
    })

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
            messages.error(request, '请选择分类、国家和至少一个模板')
            return redirect('product_create')

        country = get_object_or_404(Country, code=country_code)
        category = get_object_or_404(PrintCategory, id=int(category_id))

        for i in range(count):
            main_tid = random.choice(template_ids)
            main_template = get_object_or_404(TShirtTemplate, id=int(main_tid))
            product = Product.objects.create(
                country=country, category=category, template=main_template,
                size_info=main_template.sizes, status='processing'
            )
            for tid in template_ids:
                tpl = get_object_or_404(TShirtTemplate, id=int(tid))
                ProductSKU.objects.create(product=product, template=tpl)
            threading.Thread(target=_run_generation_v2, args=(product.id, i), daemon=True).start()

        messages.success(request, f'创建 {count} 个产品（每个 {len(template_ids)} 个SKU），正在生成...')
        return redirect('product_list')

    return render(request, 'dashboard/product_create.html', {
        'categories': categories, 'templates': templates, 'countries': countries,
    })

@staff_required
def product_edit(request, pid):
    p = get_object_or_404(Product.objects.prefetch_related('skus__template').select_related('category', 'country'), id=pid)
    if request.method == 'POST':
        p.title = request.POST.get('title', p.title)
        p.description = request.POST.get('description', p.description)
        p.size_info = request.POST.get('size_info', p.size_info)
        p.status = request.POST.get('status', p.status)
        p.save()
        messages.success(request, '已更新')
        return redirect('product_list')
    return render(request, 'dashboard/product_edit.html', {'product': p})

@staff_required
def product_delete(request, pid):
    get_object_or_404(Product, id=pid).delete()
    return redirect('product_list')

@staff_required
def product_batch_delete(request):
    ids = request.GET.getlist('ids')
    ids = [int(i) for i in ids if i.isdigit()]
    if ids: Product.objects.filter(id__in=ids).delete(); messages.success(request, f'已删除 {len(ids)} 个产品')
    return redirect('product_list')

@staff_required
def product_generate_all(request):
    products = Product.objects.filter(status__in=['pending'])
    for p in products:
        p.status = 'processing'; p.save()
        threading.Thread(target=_run_generation_v2, args=(p.id, 0), daemon=True).start()
    messages.success(request, f'已启动 {products.count()} 个产品的生成')
    return redirect('product_list')

@staff_required
def product_regenerate(request, pid):
    p = get_object_or_404(Product, id=pid)
    p.status = 'processing'; p.save()
    threading.Thread(target=_run_generation_v2, args=(p.id, 0), daemon=True).start()
    messages.success(request, '正在后台生成...')
    return redirect('product_list')

@staff_required
def product_export(request):
    ids = request.GET.getlist('ids')
    if not ids: messages.error(request, '请先选择产品'); return redirect('product_list')
    ids = [int(i) for i in ids if i.isdigit()]
    from apps.export_app.services import build_export_response
    products = Product.objects.filter(id__in=ids).select_related('country')
    countries = set(p.country.code for p in products)
    fn = f'tkerp_export_{countries.pop()}' if len(countries) == 1 else 'tkerp_export_all'
    return build_export_response(ids, filename=fn)

# ============================================================
# V2 Generation Pipeline
# ============================================================
def _run_generation_v2(product_id, variant_index):
    """V2: prompt组装 → txt2img → 多SKU"""
    # 确保后台线程能找到项目根目录
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    from apps.products.models import ProductSKU

    product = Product.objects.select_related('category', 'template').get(id=product_id)
    skus = list(ProductSKU.objects.filter(product_id=product_id).select_related('template'))
    if not skus: return

    category = product.category
    rng = random.Random(product_id * 1000 + variant_index)
    bg = rng.choice(BACKGROUNDS)
    product.background = bg
    product.seed = rng.randint(1, 999999999)
    product.save()

    seed = product.seed

    provider = ComfyUIProvider()
    for sku in skus:
        try:
            prompt = _build_product_prompt(sku.template, category, bg)
            neg = getattr(category, 'negative_prompt', '') or ''
            neg += (
                ', low quality, blurry, anime, cartoon, plain blank t-shirt, solid color t-shirt without print, '
                'no graphic, no design, empty t-shirt, wrong color t-shirt, white t-shirt, '
                'human, person, model, face, body, mannequin head, plastic fabric, polyester texture, '
                'oversaturated, bad anatomy, deformed clothing, cropped garment, watermark, logo distortion, '
                'low resolution, multiple t-shirts, t-shirt with different color'
            )
            result = provider.generate_image(prompt=prompt, params={
                'seed': seed, 'steps': 30, 'cfg_scale': 7.5, 'width': 1024, 'height': 1024,
                'negative_prompt': neg,
            })
            if result.images:
                img = result.images[0]
                buf = io.BytesIO()
                img.save(buf, format='JPEG', quality=92)
                buf.seek(0)
                sku.mockup_image.save(f'p{product_id}_sku{sku.id}.jpg', ContentFile(buf.getvalue()), save=True)
        except Exception as e:
            print(f'SKU {sku.id} gen failed: {e}')

    # Text generation
    try:
        _generate_text_v2(product_id)
        Product.objects.filter(id=product_id).update(status='completed')
    except Exception as e:
        import traceback
        Product.objects.filter(id=product_id).update(status='text_pending', error_message=str(e)[:500])
        print(f'Text gen failed for {product_id}: {e}\n{traceback.format_exc()}')

def _build_product_prompt(template, category, background):
    color_name = template.get_color_display() if hasattr(template, 'get_color_display') else template.color
    return (
        f"a single {color_name} {template.prompt_body or 'oversized t-shirt'}, "
        f"{template.fabric or 'premium heavyweight cotton, 230gsm'}, "
        f"ONLY {color_name} color fabric, MUST be {color_name} colored, "
        f"{category.print_prompt} graphic print design visible on the t-shirt, "
        f"natural fabric folds and wrinkles, realistic cotton texture, "
        f"{background}, soft indoor lighting, soft ambient light, natural daylight, "
        f"high detail fabric texture, commercial apparel photography, "
        f"ecommerce product shot, flat lay photography, no person no model, "
        f"front view, center composition, 85mm lens, "
        f"hyper realistic, photorealism, 8k, masterpiece"
    )

def _generate_text_v2(product_id):
    """用 DeepSeek 生成商品标题和描述"""
    from apps.generation.deepseek import DeepSeekProvider
    from ai.prompts.loader import build_text_prompt
    product = Product.objects.select_related('country', 'category').get(id=product_id)
    language_map = {'ID': 'id', 'TH': 'th'}
    language = language_map.get(product.country.code, 'id')
    desc = product.category.print_prompt[:100] if product.category.print_prompt else 'stylish print design'
    prompt = build_text_prompt(language=language, print_description=desc)
    provider = DeepSeekProvider()
    result = provider.generate_text(prompt, language=language)
    product.title = result.title
    product.description = result.description
    product.save()

# Import at bottom to avoid circular
from apps.generation.comfyui import ComfyUIProvider

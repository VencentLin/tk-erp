"""运营面板视图 — 完整 CRUD + AI 生成 + SKU 支持"""
import json, io, threading, sys, os
os.environ.setdefault('ORT_PROVIDERS', 'CPUExecutionProvider')  # 全局禁用 onnxruntime CUDA

from pathlib import Path
from PIL import Image
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import HttpResponse
from django.contrib.auth.models import User

from apps.patterns.models import Pattern
from apps.templates_app.models import TShirtTemplate
from apps.products.models import Product, ProductSKU
from apps.core.models import Country, Store
from apps.patterns.batch_import import batch_import_patterns

staff_required = user_passes_test(lambda u: u.is_staff, login_url='/admin/login/')
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


# ============================================================
# Settings
# ============================================================

@staff_required
def settings_page(request):
    from apps.generation.comfyui import ComfyUIProvider
    provider = ComfyUIProvider()
    models = provider.get_available_checkpoints()
    current_model = provider.model

    if request.method == 'POST':
        selected_model = request.POST.get('model', current_model)
        config_path = PROJECT_ROOT / 'data' / 'config.json'
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w') as f:
            json.dump({'comfyui_model': selected_model}, f)
        messages.success(request, f'已切换模型: {selected_model}')
        return redirect('settings_page')

    return render(request, 'dashboard/settings.html', {
        'models': models, 'current_model': current_model,
    })


# ============================================================
# Dashboard
# ============================================================

@staff_required
def index(request):
    ctx = {
        'pattern_count': Pattern.objects.filter(is_deleted=False).count(),
        'template_count': TShirtTemplate.objects.filter(is_active=True).count(),
        'product_count': Product.objects.count(),
        'completed_count': Product.objects.filter(status='completed').count(),
        'recent_patterns': Pattern.objects.filter(is_deleted=False).order_by('-created_at')[:8],
        'recent_products': Product.objects.prefetch_related('skus').order_by('-created_at')[:8],
        'countries': Country.objects.all(),
    }
    return render(request, 'dashboard/index.html', ctx)


# ============================================================
# Country & Store
# ============================================================

@staff_required
def country_list(request):
    countries = Country.objects.all()
    stores = Store.objects.select_related('country', 'owner').all()
    return render(request, 'dashboard/country_list.html', {'countries': countries, 'stores': stores})


@staff_required
def country_save(request):
    if request.method == 'POST':
        cid = request.POST.get('id')
        code = request.POST.get('code', '').strip().upper()
        name = request.POST.get('name', '').strip()
        if code and name:
            if cid:
                c = get_object_or_404(Country, id=int(cid)); c.code, c.name = code, name; c.save()
            else:
                Country.objects.create(code=code, name=name)
    return redirect('country_list')


@staff_required
def country_delete(request, cid):
    Country.objects.filter(id=cid).delete()
    return redirect('country_list')


@staff_required
def store_save(request):
    if request.method == 'POST':
        sid = request.POST.get('id')
        country = get_object_or_404(Country, id=int(request.POST['country_id']))
        name = request.POST.get('name', '').strip()
        if name:
            if sid:
                s = get_object_or_404(Store, id=int(sid)); s.name, s.country, s.owner = name, country, request.user; s.save()
            else:
                Store.objects.create(name=name, country=country, owner=request.user)
    return redirect('country_list')


@staff_required
def store_delete(request, sid):
    Store.objects.filter(id=sid).delete()
    return redirect('country_list')


# ============================================================
# User Management
# ============================================================

@staff_required
def user_list(request):
    users = User.objects.select_related('profile').all()
    return render(request, 'dashboard/user_list.html', {'users': users})


@staff_required
def user_save(request):
    if request.method == 'POST':
        uid = request.POST.get('id')
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        role = request.POST.get('role', 'operator')
        if uid:
            u = get_object_or_404(User, id=int(uid))
            u.username = username
            if password:
                u.set_password(password)
            u.profile.role = role
            u.profile.save()
            u.save()
        elif username and password:
            u = User.objects.create_user(username=username, password=password)
            u.profile.role = role
            u.profile.save()
    return redirect('user_list')


@staff_required
def user_delete(request, uid):
    if request.user.id != int(uid):
        User.objects.filter(id=uid).delete()
    return redirect('user_list')


# ============================================================
# Pattern
# ============================================================

@staff_required
def pattern_list(request):
    patterns = Pattern.objects.filter(is_deleted=False).order_by('-created_at')
    return render(request, 'dashboard/pattern_list.html', {'patterns': patterns})


@staff_required
def pattern_upload(request):
    if request.method == 'POST':
        files = request.FILES.getlist('images')
        for f in files:
            if f.size > 0:
                Pattern.objects.create(image=f, uploaded_by=request.user,
                                       source_type='', note=f.name)
        messages.success(request, f'上传 {len(files)} 张成功')
        return redirect('pattern_list')
    return render(request, 'dashboard/pattern_upload.html')


@staff_required
def pattern_edit(request, pid):
    p = get_object_or_404(Pattern, id=pid)
    if request.method == 'POST':
        p.source_type = request.POST.get('source_type', p.source_type)
        p.note = request.POST.get('note', p.note)
        if request.FILES.get('image'):
            p.image = request.FILES['image']
        p.save()
        messages.success(request, '已更新')
        return redirect('pattern_list')
    return render(request, 'dashboard/pattern_edit.html', {'pattern': p})


@staff_required
def pattern_delete(request, pid):
    p = get_object_or_404(Pattern, id=pid)
    p.is_deleted = True; p.save()
    return redirect('pattern_list')


@staff_required
def pattern_batch(request):
    ctx = {'results': None, 'error': None}
    if request.method == 'POST':
        try:
            uploaded_files = request.FILES.getlist('images')
            excel_file = request.FILES.get('excel_file')
            excel_data = excel_file.read() if (excel_file and excel_file.size > 0) else None
            results = batch_import_patterns(
                files=uploaded_files or None, excel_file=excel_data, uploaded_by=request.user,
            )
            ctx.update(results=results, new_count=sum(1 for r in results if r.status == 'new'),
                       dup_count=sum(1 for r in results if r.status == 'duplicate'),
                       err_count=sum(1 for r in results if r.status == 'error'))
            messages.success(request, f'导入完成: {ctx["new_count"]} 新增, {ctx["dup_count"]} 重复, {ctx["err_count"]} 失败')
        except Exception as e:
            import traceback; ctx['error'] = f'{type(e).__name__}: {e}\n{traceback.format_exc()}'
    return render(request, 'dashboard/pattern_batch.html', ctx)


# ============================================================
# Template
# ============================================================

@staff_required
def template_list(request):
    templates = TShirtTemplate.objects.filter(is_active=True).order_by('-created_at')
    return render(request, 'dashboard/template_list.html', {'templates': templates})


@staff_required
def template_upload(request):
    if request.method == 'POST':
        name = request.POST.get('name', '')
        color = request.POST.get('color', 'white')
        image = request.FILES.get('image')
        if image and name:
            # 自动去背景
            img_data = _remove_bg_from_upload(image)
            tpl = TShirtTemplate(name=name, color=color)
            tpl.image.save(image.name, img_data, save=True)
            messages.success(request, '模板上传成功（已自动去背景）')
            return redirect('template_list')
    return render(request, 'dashboard/template_upload.html')


@staff_required
def template_edit(request, tid):
    t = get_object_or_404(TShirtTemplate, id=tid)
    if request.method == 'POST':
        t.name = request.POST.get('name', t.name)
        t.color = request.POST.get('color', t.color)
        if request.FILES.get('image'):
            img_data = _remove_bg_from_upload(request.FILES['image'])
            t.image.save(request.FILES['image'].name, img_data, save=False)
        t.is_active = request.POST.get('is_active') == 'on'
        t.save()
        messages.success(request, '已更新')
        return redirect('template_list')
    return render(request, 'dashboard/template_edit.html', {'template': t})


def _remove_bg_from_upload(uploaded_file):
    """对上传的文件进行抠图，返回 ContentFile"""
    from PIL import Image as PILImage
    from rembg import remove
    from django.core.files.base import ContentFile

    img = PILImage.open(uploaded_file).convert('RGBA')
    result = remove(img)
    buf = io.BytesIO()
    result.save(buf, format='PNG')
    buf.seek(0)
    return ContentFile(buf.getvalue())


@staff_required
def template_delete(request, tid):
    t = get_object_or_404(TShirtTemplate, id=tid)
    t.is_active = False
    t.save()
    return redirect('template_list')


# ============================================================
# Product
# ============================================================

@staff_required
def product_list(request):
    country_code = request.GET.get('country', '')
    status = request.GET.get('status', '')
    products = Product.objects.prefetch_related('skus__template').select_related('country', 'pattern').order_by('-created_at')
    if country_code: products = products.filter(country__code=country_code)
    if status: products = products.filter(status=status)
    return render(request, 'dashboard/product_list.html', {
        'products': products, 'countries': Country.objects.all(),
        'statuses': Product.STATUS_CHOICES,
        'selected_country': country_code, 'selected_status': status,
    })


@staff_required
def product_create(request):
    patterns = Pattern.objects.filter(is_deleted=False).order_by('-created_at')
    templates = TShirtTemplate.objects.filter(is_active=True)
    countries = Country.objects.all()

    if request.method == 'POST':
        pattern_ids = request.POST.getlist('patterns')
        country_code = request.POST.get('country')
        template_ids = request.POST.getlist('templates')
        variant_count = int(request.POST.get('variant_count', 1))
        action = request.POST.get('action', 'create')

        if not pattern_ids or not country_code or not template_ids:
            messages.error(request, '请选择印花、国家和至少一个模板')
            return redirect('product_create')

        country = get_object_or_404(Country, code=country_code)
        created = 0
        for pid in pattern_ids:
            pattern = get_object_or_404(Pattern, id=int(pid))
            # 每个变体方向 = 一个独立产品
            for v in range(variant_count):
                product = Product.objects.create(
                    country=country, pattern=pattern,
                    status='processing' if action == 'generate' else 'pending'
                )
                for tid in template_ids:
                    template = get_object_or_404(TShirtTemplate, id=int(tid))
                    ProductSKU.objects.create(product=product, template=template)
                created += 1

                if action == 'generate':
                    threading.Thread(target=_run_pipeline_sync,
                                     args=(pattern.id, product.id, pattern.source_type == 'clean_print', v),
                                     daemon=True).start()

        msg = f'创建 {created} 个产品'
        if len(template_ids) > 1: msg += f'（每个 {len(template_ids)} 个SKU）'
        if variant_count > 1: msg += f'（每印花 {variant_count} 个变体）'
        messages.success(request, msg)
        return redirect('product_list')

    return render(request, 'dashboard/product_create.html', {
        'patterns': patterns, 'templates': templates, 'countries': countries,
    })


@staff_required
def product_edit(request, pid):
    p = get_object_or_404(Product.objects.prefetch_related('skus__template'), id=pid)
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
def product_generate_all(request):
    products = Product.objects.filter(status__in=['pending', 'text_pending']).select_related('pattern')
    for p in products:
        p.status = 'processing'; p.save()
        threading.Thread(target=_run_pipeline_sync,
                         args=(p.pattern_id, p.id, p.pattern.source_type == 'clean_print'),
                         daemon=True).start()
    messages.success(request, f'已启动 {products.count()} 个产品的生成')
    return redirect('product_list')


@staff_required
def product_regenerate(request, pid):
    p = get_object_or_404(Product, id=pid)
    p.status = 'processing'; p.save()
    threading.Thread(target=_run_pipeline_sync,
                     args=(p.pattern_id, p.id, p.pattern.source_type == 'clean_print'),
                     daemon=True).start()
    messages.success(request, '正在后台生成中...')
    return redirect('product_list')


@staff_required
def product_batch_delete(request):
    ids = request.GET.getlist('ids')
    ids = [int(i) for i in ids if i.isdigit()]
    if ids:
        Product.objects.filter(id__in=ids).delete()
        messages.success(request, f'已删除 {len(ids)} 个产品')
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
# Pipeline (background thread)
# ============================================================

def _run_pipeline_sync(pattern_id, product_id, skip_preprocess, variant_index=0):
    """后台线程执行生成流水线"""
    project_root = str(PROJECT_ROOT)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    os.environ.setdefault('ORT_PROVIDERS', 'CPUExecutionProvider')

    try:
        # Step 1: 预处理
        if not skip_preprocess:
            try:
                from celery_app.preprocessing import remove_background_task
                remove_background_task(pattern_id)
            except Exception as e:
                print(f'Preprocessing failed: {e}')

        # Step 2: 生成一张印花图（不同变体用不同seed）
        try:
            _generate_single_print(pattern_id, product_id, variant_index)
        except Exception as e:
            Product.objects.filter(id=product_id).update(status='failed', error_message=str(e))
            print(f'Image gen failed for product {product_id}: {e}')
            return

        # Step 3: 将印花贴到每个SKU的T恤模板上
        _composite_mockups(product_id)

        # Step 4: 文本生成
        try:
            from celery_app.text_gen import generate_product_text_task
            generate_product_text_task(product_id)
        except Exception as e:
            Product.objects.filter(id=product_id).update(status='text_pending', error_message=str(e))
            print(f'Text gen failed for product {product_id}: {e}')

    except Exception as e:
        Product.objects.filter(id=product_id).update(status='failed', error_message=str(e))


def _analyze_print(image_data: bytes) -> str:
    """用豆包 Vision API 分析印花特征，返回描述 prompt"""
    import base64, requests, json as json_mod
    from django.conf import settings

    img_b64 = base64.b64encode(image_data).decode()

    resp = requests.post(
        f'{settings.DEEPSEEK_BASE_URL}/chat/completions',
        headers={
            'Authorization': f'Bearer {settings.DEEPSEEK_API_KEY}',
            'Content-Type': 'application/json',
        },
        json={
            'model': 'doubao-seed-2.0-lite',
            'messages': [{
                'role': 'user',
                'content': [
                    {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{img_b64}'}},
                    {'type': 'text', 'text': (
                        'Describe this T-shirt PRINT DESIGN in detail. Focus ONLY on the print pattern itself, '
                        'ignore the T-shirt, model, background, and clothing. Describe: style (e.g. floral, geometric, '
                        'streetwear, vintage), pattern type, color scheme, composition, and artistic technique. '
                        'Write a concise English prompt (max 80 words) suitable for Stable Diffusion to generate '
                        'a brand new similar-style print design. The output should be a clean seamless pattern on '
                        'transparent background, print-ready for apparel.'
                    )},
                ]
            }],
            'max_tokens': 200,
            'temperature': 0.7,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data['choices'][0]['message']['content'].strip()


def _generate_single_print(pattern_id, product_id, variant_index=0):
    """豆包分析印花 → ComfyUI txt2img 全新生成 → 贴到模板"""
    import time, random, io as io_mod
    from PIL import Image as PILImage
    from apps.patterns.models import Pattern
    from apps.products.models import Product, GenerationLog
    from apps.generation.comfyui import ComfyUIProvider
    from django.core.files.base import ContentFile

    pattern = Pattern.objects.get(id=pattern_id)
    product = Product.objects.get(id=product_id)

    if not pattern.image:
        return

    provider = ComfyUIProvider()
    t0 = time.time()
    rng = random.Random(product_id * 1000 + variant_index)

    # Step 1: 豆包分析印花特征
    try:
        base_description = _analyze_print(pattern.image.read())
    except Exception as e:
        base_description = 'a stylish seamless t-shirt print design, vector art, vibrant colors'

    # Step 2: 加入变体变化
    color_variations = [
        'with a refreshed color palette of warm tones',
        'with a refreshed color palette of cool tones',
        'with a pastel color scheme',
        'with bold high-contrast colors',
        'with earthy natural colors',
        'with neon vibrant colors',
        'with monochrome palette',
        'with jewel-tone colors',
    ]
    color_hint = color_variations[variant_index % len(color_variations)]

    pos_prompt = (
        f"{base_description}. {color_hint}. "
        f"Clean seamless pattern, vector illustration, on solid single-color background, "
        f"crisp edges, print-ready for t-shirt, professional apparel graphic design."
    )

    neg_prompt = (
        "photorealistic, 3D render, human, person, face, body, clothing, t-shirt, "
        "fabric, wrinkled, photo of, mockup, mannequin, watermark, logo, "
        "blurry, low quality, messy edges, white background, black background, "
        "gray background, dark background"
    )

    # Step 3: txt2img 全新生成（不用 img2img，不会有"重印T恤"问题）
    params = {
        'steps': 30,
        'cfg_scale': 7.5,
        'seed': rng.randint(1, 999999999),
        'width': 1024,
        'height': 1024,
    }

    result = provider.generate_image(prompt=pos_prompt, params=params)

    if result.images:
        img = result.images[0]
        # Step 4: 去白色/浅色背景，保留印花细节
        img = _make_bg_transparent(img)
        buf = io_mod.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        product.print_image.save(f'product_{product_id}_print.png', ContentFile(buf.getvalue()), save=True)

    duration = int((time.time() - t0) * 1000)
    GenerationLog.objects.create(
        product=product, step='image_gen', model_used=f'{provider.model} + doubao-seed-2.0-lite',
        params={
            'variant_index': variant_index,
            'base_description': base_description[:200],
            'seed': params['seed'],
        },
        duration_ms=duration,
    )


def _make_bg_transparent(img, tolerance=30):
    """泛洪填充去背景：从四角采样背景色，泛洪移除"""
    img = img.convert('RGBA')
    w, h = img.size
    pixels = img.load()

    # 从四角采样背景色
    corners = [(0, 0), (w-1, 0), (0, h-1), (w-1, h-1)]
    bg_colors = [pixels[x, y][:3] for x, y in corners]

    def is_bg(r, g, b):
        """判断像素是否接近任一角落的背景色"""
        for br, bg_c, bb in bg_colors:
            if abs(r-br) < tolerance and abs(g-bg_c) < tolerance and abs(b-bb) < tolerance:
                return True
        return False

    # 从边缘开始泛洪
    from collections import deque
    visited = set()
    q = deque()
    for x in range(w):
        q.append((x, 0)); q.append((x, h-1))
    for y in range(1, h-1):
        q.append((0, y)); q.append((w-1, y))

    while q:
        x, y = q.popleft()
        if (x, y) in visited or x < 0 or x >= w or y < 0 or y >= h:
            continue
        r, g, b, a = pixels[x, y]
        if is_bg(r, g, b):
            visited.add((x, y))
            pixels[x, y] = (r, g, b, 0)
            for dx, dy in [(1,0), (-1,0), (0,1), (0,-1)]:
                q.append((x+dx, y+dy))

    return img


def _composite_mockups(product_id):
    """将生成的印花贴到每个SKU的T恤模板上"""
    from apps.products.models import ProductSKU
    from django.core.files.base import ContentFile

    product = Product.objects.get(id=product_id)
    if not product.print_image:
        return

    # 读取印花图
    print_img = Image.open(product.print_image).convert('RGBA')
    skus = ProductSKU.objects.filter(product_id=product_id).select_related('template')

    for sku in skus:
        try:
            if not sku.template.image:
                continue

            # 读取模板图
            template_img = Image.open(sku.template.image).convert('RGBA')

            # 计算印花在T恤上的位置和大小（居中偏上，约占40%宽度）
            tw, th = template_img.size
            pw = int(tw * 0.4)
            ph = int(print_img.height * (pw / print_img.width))
            resized_print = print_img.resize((pw, ph), Image.LANCZOS)

            # 位置：水平居中，垂直约30%处
            px = (tw - pw) // 2
            py = int(th * 0.3)

            # 合成
            result = template_img.copy()
            result.paste(resized_print, (px, py), resized_print)

            # 保存
            buf = io.BytesIO()
            result.save(buf, format='PNG')
            buf.seek(0)
            sku.mockup_image.save(f'sku_{sku.id}_mockup.png', ContentFile(buf.getvalue()), save=True)

        except Exception as e:
            print(f'Mockup composite failed for SKU {sku.id}: {e}')

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
from apps.categories.models import PrintCategory, PromptPreset, PrintDesignPreset, PrintDesign

staff_required = user_passes_test(lambda u: u.is_staff, login_url='/admin/login/')
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CATEGORY_MD_DIR = Path(__file__).resolve().parent.parent / 'categories' / 'prompts'
TEMPLATE_DIR = PROJECT_ROOT / 'data' / 'prompts' / 'base'

# ============================================================
# V6 Architecture — 固定 Prompt 组件
# ============================================================
SYSTEM_PROMPT = (
    'You are generating ecommerce apparel product photography.\n'
    'The garment is always the primary subject.\n'
    'The garment must occupy most of the image.\n'
    'Graphics must be physically printed on the garment fabric.\n'
    'Graphics must follow fabric folds.\n'
    'Graphics are attached to the garment surface.\n'
    'Never generate standalone artwork.\n'
    'Never generate posters.\n'
    'Never generate illustrations.\n'
    'Never generate floating graphics.\n'
    'Never generate isolated prints.\n'
    'Always generate a real apparel product photo.\n'
    'The final image must look like a Taobao clothing listing photo.'
)

V6_NEGATIVE_PROMPT = (
    'poster, canvas, illustration, standalone artwork, '
    'floating graphic, detached print, sticker, logo only, '
    'wall art, framed picture, art print, '
    'human, person, face, body, fashion model, '
    'anime character, manga, cartoon screenshot, game screenshot, '
    'watermark, text overlay, low quality, blurry, '
    # V7.1: 禁止拼色/口袋/立体印花
    'two-tone shirt, color-block shirt, contrast sleeves, raglan sleeves, '
    'beige body panel, diagonal stripe, large diagonal band, '
    'oversized print, large print, full shirt print, all-over print, '
    'back print, print touching sleeves, print crossing side seams, '
    'print reaching collar, print reaching hem, '
    'chest pocket, shirt pocket, real pocket, sewn pocket, '
    'embroidered patch, embroidery, raised embroidery, '
    '3d print, raised print, thick applique, applique, '
    'fabric patch, sewn-on badge, puffy print, rubber patch'
)

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
        'recent_products': Product.objects.prefetch_related('skus').select_related('category', 'country', 'prompt_preset').order_by('-created_at')[:8],
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
        t.is_pod_template = request.POST.get('is_pod_template') == 'on'
        if t.is_pod_template:
            t.print_area_x = request.POST.get('print_area_x') or None
            t.print_area_y = request.POST.get('print_area_y') or None
            t.print_area_width = request.POST.get('print_area_width') or None
            t.print_area_height = request.POST.get('print_area_height') or None
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

# ============================================================
# V5.2 Whitelist JSON Sanitizer — 白名单机制，杜绝污染
# ============================================================
_TEMPLATE_ALLOWED_KEYS = {
    'product_category', 'primary_color', 'fit',
    'neckline', 'sleeve_type', 'print_area',
}
_STYLE_ALLOWED_KEYS = {
    'background_type', 'background_elements',
    'lighting_type', 'color_palette',
}


def _sanitize_json_whitelist(data, allowed_keys):
    """V5.2: 白名单 — 只保留允许的 key，其余全部丢弃"""
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if k in allowed_keys}


def _style_json_to_text(data: dict) -> str:
    """V5.2: 将白名单 style JSON 转为纯文本（仅环境，无人物/服装）"""
    parts = []
    bg_type = data.get('background_type', '')
    if bg_type:
        parts.append(f'{bg_type} background')
    bg_elements = data.get('background_elements', [])
    if isinstance(bg_elements, list):
        for el in bg_elements:
            parts.append(str(el).replace('_', ' '))
    elif isinstance(bg_elements, str):
        parts.append(bg_elements.replace('_', ' '))
    lighting = data.get('lighting_type', '')
    if lighting:
        parts.append(f'{lighting} lighting')
    palette = data.get('color_palette', [])
    if isinstance(palette, list) and palette:
        parts.append('environment colors: ' + ', '.join(str(c).replace('_', ' ') for c in palette))
    elif isinstance(palette, str) and palette:
        parts.append(f'environment colors: {palette}')
    return ', '.join(parts) if parts else ''


def _sanitize_style_context(text):
    """V5.2: 保留兼容旧文本字段的清理逻辑"""
    if not text:
        return ''
    # 如果是 JSON，用白名单解析
    import json as _json
    try:
        data = _json.loads(text) if isinstance(text, str) else text
        if isinstance(data, dict):
            clean = _sanitize_json_whitelist(data, _STYLE_ALLOWED_KEYS)
            return _style_json_to_text(clean) or text
    except (_json.JSONDecodeError, TypeError):
        pass
    return text


def _sanitize_product_identity(text):
    """V5.2: 解析 JSON product_identity → 白名单 → 文本 + lock 字段"""
    if not text:
        return ''
    import json as _json
    try:
        data = _json.loads(text) if isinstance(text, str) else text
        if isinstance(data, dict):
            clean = _sanitize_json_whitelist(data, _TEMPLATE_ALLOWED_KEYS)
            lines = []
            if clean.get('primary_color') and clean.get('product_category'):
                cat = clean['product_category'].replace('tshirt', 't-shirt')
                lines.append(f'{clean["primary_color"]} {cat}')
            if clean.get('fit'):
                lines.append(f'{clean["fit"]} fit')
            if clean.get('neckline'):
                lines.append(f'{clean["neckline"].replace("_", " ")}')
            if clean.get('sleeve_type'):
                lines.append(f'{clean["sleeve_type"].replace("_", " ")}')
            lines.append('heavyweight cotton')
            lines.append('realistic cotton texture')
            lines.append('natural fabric folds')
            if clean.get('print_area'):
                lines.append(f'{clean["print_area"].replace("_", " ")} graphic print')
            lock_lines = [
                'lock_color: true', 'lock_fit: true',
                'lock_product_category: true', 'lock_print_placement: true',
            ]
            return ',\n'.join(lines + lock_lines)
    except (_json.JSONDecodeError, TypeError):
        pass
    # Fallback for old text format: 清理双逗号，避免重复 lock 字段
    text = text.replace(',,', ',').replace(',\n,', ',')
    if 'lock_color' not in text.lower():
        text = text.rstrip(',\n ') + ',\nlock_color: true,\nlock_fit: true,\nlock_product_category: true,\nlock_print_placement: true'
    return text


def _detect_human_in_style(text):
    """V5.2: 检测 style JSON 或文本是否含人物"""
    if not text:
        return False
    text_lower = text.lower()
    return any(kw in text_lower for kw in [
        'human', 'person', 'people', 'man', 'woman', 'model',
        'portrait', 'face', 'body', 'hand', 'legs', 'arms',
        'fashion', 'editorial', 'lifestyle',
    ])


def _analyze_template(image_data: bytes) -> str:
    """V5.2 Stage 1: 模板识别器 → JSON → 白名单 sanitize → 文本"""
    import base64, requests, json as json_mod
    img_b64 = base64.b64encode(image_data).decode()
    resp = requests.post(
        f'{settings.DEEPSEEK_BASE_URL}/chat/completions',
        headers={'Authorization': f'Bearer {settings.DEEPSEEK_API_KEY}', 'Content-Type': 'application/json'},
        json={'model': 'doubao-seed-2.0-lite', 'messages': [{'role': 'user', 'content': [
            {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{img_b64}'}},
            {'type': 'text', 'text': (
                '你是服装模板识别器。\n'
                '请识别模板的:\n'
                '  - product_category\n'
                '  - primary_color\n'
                '  - fit\n'
                '  - neckline\n'
                '  - sleeve_type\n'
                '  - print_area\n\n'
                '禁止输出:\n'
                '  background, lighting, scene, model, person, style, photography\n\n'
                '输出 ONLY valid JSON, no other text:\n'
                '{\n'
                '  "product_category": "tshirt",\n'
                '  "primary_color": "black",\n'
                '  "fit": "oversized",\n'
                '  "neckline": "crew_neck",\n'
                '  "sleeve_type": "short_sleeve",\n'
                '  "print_area": "center_chest"\n'
                '}\n\n'
                'Values:\n'
                '- product_category: tshirt, polo, hoodie, sweatshirt, tank_top\n'
                '- primary_color: black, white, gray, navy, beige, brown, green, olive, red, pink, purple, yellow, orange, sky_blue\n'
                '- fit: oversized, regular, boxy, relaxed, slim\n'
                '- neckline: crew_neck, v_neck, mock_neck, polo_collar, hooded\n'
                '- sleeve_type: short_sleeve, long_sleeve, sleeveless\n'
                '- print_area: center_chest, left_chest, full_front, back, full_back, sleeve'
            )}
        ]}], 'max_tokens': 150}, timeout=60)
    resp.raise_for_status()
    text = resp.json()['choices'][0]['message']['content'].strip()
    if text.startswith('```'): text = text.split('\n', 1)[1].rsplit('```', 1)[0]
    try:
        data = json_mod.loads(text)
        # V5.2 whitelist sanitize
        data = _sanitize_json_whitelist(data, _TEMPLATE_ALLOWED_KEYS)
        return _sanitize_product_identity(json_mod.dumps(data))
    except (json_mod.JSONDecodeError, KeyError):
        if 'PRODUCT_IDENTITY:' in text:
            text = text.split('PRODUCT_IDENTITY:', 1)[1].strip()
        return _sanitize_product_identity(text)

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

            created_count, updated_count, human_count = 0, 0, 0
            for cat_data in categories:
                slug = cat_data['name'].lower().replace(' ', '-').replace('/', '-')
                # V5.2: style_json (whitelist) → text; 兼容旧 style_context
                raw_print = cat_data.get('print_prompt', '')
                style_json = cat_data.get('style_json', {})
                if style_json and isinstance(style_json, dict):
                    clean_json = _sanitize_json_whitelist(style_json, _STYLE_ALLOWED_KEYS)
                    clean_style = _style_json_to_text(clean_json)
                    has_human = False  # whitelist 保证不会有
                else:
                    raw_style = cat_data.get('style_context', '')
                    clean_style = _sanitize_style_context(raw_style)
                    has_human = _detect_human_in_style(raw_style)

                if has_human:
                    human_count += 1

                existing = PrintCategory.objects.filter(
                    Q(name__iexact=cat_data['name']) | Q(slug=slug)
                ).first()
                if existing:
                    existing.keywords = ', '.join(set(existing.keywords.split(', ') + cat_data['keywords']))
                    existing.print_prompt = raw_print
                    existing.style_context = clean_style
                    existing.extra_prompt = cat_data.get('extra_prompt', '')
                    existing.save()
                    _update_category_md(existing)
                    updated_count += 1
                else:
                    PrintCategory.objects.create(
                        name=cat_data['name'], slug=slug,
                        keywords=', '.join(cat_data['keywords']),
                        print_prompt=raw_print,
                        style_context=clean_style,
                        extra_prompt=cat_data.get('extra_prompt', ''),
                    )
                    # .md file
                    cat = PrintCategory.objects.get(slug=slug)
                    _create_category_md(cat)
                    created_count += 1

            task.result = {'collected': ok_count, 'duplicates': dup_count, 'errors': err_count,
                           'created': created_count, 'updated': updated_count,
                           'human_detected': human_count}
            task.progress = f'Step 4/4: 完成！{created_count} 新分类 + {updated_count} 更新（{human_count} 个检测到人物已过滤）'
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

@staff_required
def category_batch_delete(request):
    ids = request.GET.getlist('ids')
    ids = [int(i) for i in ids if i.isdigit()]
    if ids:
        PrintCategory.objects.filter(id__in=ids).update(is_active=False)
        messages.success(request, f'已停用 {len(ids)} 个分类')
    return redirect('category_list')

@staff_required
def category_hard_delete(request, cid):
    """彻底删除分类（含 .md 文件），有关联产品时阻止"""
    cat = get_object_or_404(PrintCategory, id=cid)
    product_count = cat.products.count()
    if product_count > 0:
        messages.error(request, f'「{cat.name}」下有 {product_count} 个产品，请先删除产品再删除分类')
        return redirect('category_list')
    _remove_category_md(cat)
    cat.delete()
    messages.success(request, f'已彻底删除「{cat.name}」')
    return redirect('category_list')

@staff_required
def category_batch_hard_delete(request):
    """批量彻底删除分类"""
    ids = request.GET.getlist('ids')
    ids = [int(i) for i in ids if i.isdigit()]
    if not ids:
        return redirect('category_list')
    categories = PrintCategory.objects.filter(id__in=ids)
    blocked, deleted = [], []
    for cat in categories:
        if cat.products.count() > 0:
            blocked.append(cat.name)
        else:
            _remove_category_md(cat)
            cat.delete()
            deleted.append(cat.name)
    if deleted:
        messages.success(request, f'已彻底删除 {len(deleted)} 个分类')
    if blocked:
        messages.error(request, f'以下分类有关联产品，无法删除：{", ".join(blocked)}')
    return redirect('category_list')

def _remove_category_md(category):
    """删除分类对应的 .md 文件"""
    if category.prompt_file:
        md_path = PROJECT_ROOT / category.prompt_file
        if md_path.exists():
            md_path.unlink()

@staff_required
def category_batch_regenerate(request):
    """批量重新生成分类的 .md 文件和 negative_prompt"""
    ids = request.GET.getlist('ids')
    ids = [int(i) for i in ids if i.isdigit()]
    if ids:
        categories = PrintCategory.objects.filter(id__in=ids)
        count = 0
        for cat in categories:
            _create_category_md(cat)
            count += 1
        messages.success(request, f'已重新生成 {count} 个分类的 Prompt 文件')
    return redirect('category_list')

# ============================================================
# Prompt Preset Management — 直接上传 .md 提示词
# ============================================================
_PROMPT_MD_DIR = PROJECT_ROOT / 'data' / 'prompts'


def _parse_md_prompt(content: str) -> tuple:
    """V7: 解析 .md 文件 → (positive_prompt, negative_prompt)"""
    positive = content
    negative = ''

    # V7 分割: NEGATIVE 段
    neg_markers = ['## NEGATIVE', '## Negative', '## 负面 Prompt', '## 负面提示词']
    for marker in neg_markers:
        if marker in content:
            parts = content.split(marker, 1)
            positive = parts[0].strip()
            if len(parts) > 1:
                negative = parts[1].strip()
            break

    # Fallback: 旧的 --- 分割
    if not negative and '---' in content:
        parts = content.split('---', 1)
        positive = parts[0].strip()
        if len(parts) > 1:
            negative = parts[1].strip()

    # 清理 markdown 标题（保留内容，去掉 ## 行头）
    positive = _strip_md_headers(positive)
    negative = _strip_md_headers(negative)

    return positive, negative


def _strip_md_headers(text: str) -> str:
    """去掉 ## 标题行，仅保留正文内容（发送给 SDXL 时调用）"""
    if not text:
        return ''
    lines = []
    for line in text.split('\n'):
        stripped = line.strip()
        # 跳过纯标题行（以 # 开头）
        if stripped.startswith('#'):
            continue
        # 跳过空行和分隔线
        if not stripped or stripped == '---':
            continue
        lines.append(stripped)
    return '\n'.join(lines).strip()


def _normalize_preset_prompt(text: str) -> str:
    """V7: 替换 .md 中遗留的占位符为稳定的默认服装描述，防止占位符原样进入 ComfyUI"""
    if not text:
        return text
    text = text.replace(
        '{{template_prompt}}',
        'white cotton t-shirt, crew neck, short sleeve, regular fit, '
        'realistic fabric texture, natural folds, large printable area'
    )
    text = text.replace('{{fabric}}', 'cotton fabric')
    text = text.replace('{{background}}',
        'wooden hanger, closet background, warm indoor lighting')
    return text


def _detect_shirt_color(filename: str, dir_path: str = '') -> str:
    """V7: 从文件名/目录名识别 T 恤颜色"""
    combined = (dir_path + '/' + filename).lower()
    if 'black' in combined:
        return 'black'
    if 'white' in combined:
        return 'white'
    return 'other'


def _apply_shirt_color_lock(prompt: str, shirt_color: str) -> str:
    """V7: 根据 preset.shirt_color 在 prompt 前强制锁定服装颜色"""
    if shirt_color == 'black':
        lock = 'The garment color is locked: black cotton t-shirt.'
    elif shirt_color == 'white':
        lock = 'The garment color is locked: white cotton t-shirt.'
    else:
        return prompt
    return lock + '\n' + prompt


def _apply_print_placement_lock(prompt: str, shirt_color: str) -> str:
    """V7.1: 纯色锁定 + 印花限制在胸口安全区域"""
    if shirt_color == 'black':
        color_lock = (
            'The garment is a solid black cotton t-shirt from collar to hem. '
            'Sleeves, shoulders, side panels, collar, and body are all the same black fabric. '
            'No beige body panel. No color-block garment construction. No two-tone shirt.'
        )
    elif shirt_color == 'white':
        color_lock = (
            'The garment is a solid white cotton t-shirt from collar to hem. '
            'Sleeves, shoulders, side panels, collar, and body are all the same white fabric. '
            'No color-block garment construction. No two-tone shirt.'
        )
    else:
        color_lock = (
            'The garment is a solid color cotton t-shirt from collar to hem. '
            'No color-block garment construction. No two-tone shirt.'
        )

    placement_lock = (
        'The graphic print is chest-only. '
        'The print stays inside the front torso safe area. '
        'The print is no wider than 30 percent of the front body width. '
        'The print is no taller than 25 percent of the front body height. '
        'The print must stay far away from sleeves, shoulder seams, collar, side seams, and hem. '
        'Centered front view.'
    )
    return color_lock + '\n' + placement_lock + '\n' + prompt


def _apply_flat_print_lock(prompt: str) -> str:
    """V7.1: 强制平面油墨印花，禁止口袋/刺绣/贴布/3D"""
    flat_lock = (
        'The graphic is a flat ink print directly on the cotton fabric. '
        'No pocket. No chest pocket. No sewn pocket. '
        'No embroidery. No embroidered patch. No applique. '
        'No raised print. No 3D print. No thick rubber patch. '
        'The print has no physical thickness.'
    )
    return flat_lock + '\n' + prompt


def _normalize_risky_keywords(text: str) -> tuple:
    """V7.1: 标准化高风险词为安全表达，返回 (normalized_text, warnings)"""
    warnings = []
    replacements = [
        ('back print', 'chest print'),
        ('center back', 'center chest'),
        ('upper back', 'upper chest'),
        ('full back', 'center chest'),
        ('large graphic print', 'small to medium graphic print'),
        ('large graphic', 'small to medium graphic'),
        ('oversized print', 'small chest print'),
        ('all-over print', 'chest print'),
        ('full shirt print', 'chest print'),
        ('embroidered patch', 'flat ink print'),
        ('embroidery', 'flat ink print'),
        ('stitched patch', 'flat ink print'),
        ('applique', 'flat ink print'),
        ('3d print', 'flat ink print'),
        ('raised print', 'flat ink print'),
        ('rubber patch', 'flat ink print'),
        ('puffy print', 'flat ink print'),
        ('sewn-on badge', 'flat printed emblem'),
        ('patch-like', 'flat graphic'),
        ('diagonal crossing stroke', 'curved abstract stroke'),
        ('large diagonal band', 'small curved accent'),
        ('screen-print texture', 'flat ink texture'),
        ('sewn badge', 'flat printed emblem'),
    ]
    result = text
    for old, new in replacements:
        if old in result.lower():
            result = result.replace(old, new)
            if old not in warnings:
                warnings.append(old)
    return result, warnings


@staff_required
def preset_list(request):
    color = request.GET.get('color', '')
    # V7: 首次加载或手动触发时从磁盘同步
    if request.GET.get('sync') == '1' or not PromptPreset.objects.exists():
        from apps.categories.prompt_sync import sync_prompt_presets_from_disk
        sync_prompt_presets_from_disk()
    presets = PromptPreset.objects.all().order_by('-created_at')
    if color in ('white', 'black', 'other'):
        presets = presets.filter(shirt_color=color)
    return render(request, 'dashboard/preset_list.html', {
        'presets': presets,
        'selected_color': color,
    })


@staff_required
def preset_upload(request):
    if request.method == 'POST':
        md_files = request.FILES.getlist('md_files')
        if not md_files:
            messages.error(request, '请选择 .md 文件')
            return redirect('preset_upload')

        created = 0
        for f in md_files:
            if not f.name.endswith('.md'):
                continue
            content = f.read().decode('utf-8', errors='replace')
            positive, negative = _parse_md_prompt(content)
            positive = _normalize_preset_prompt(positive)  # V7: 替换遗留占位符
            positive, _warnings = _normalize_risky_keywords(positive)  # V7.1: 标准化高风险词

            name = f.name.replace('.md', '').replace('-', ' ').replace('_', ' ').strip()
            slug = name.lower().replace(' ', '-').replace('/', '-')
            # 确保 slug 唯一
            base_slug = slug
            counter = 1
            while PromptPreset.objects.filter(slug=slug).exists():
                slug = f'{base_slug}-{counter}'
                counter += 1

            _PROMPT_MD_DIR.mkdir(parents=True, exist_ok=True)
            filepath = _PROMPT_MD_DIR / f'{slug}.md'
            filepath.write_text(content, encoding='utf-8')

            shirt_color = _detect_shirt_color(f.name)
            PromptPreset.objects.create(
                name=name, slug=slug,
                content=positive, negative_prompt=negative,
                md_file=str(filepath.relative_to(PROJECT_ROOT)),
                shirt_color=shirt_color,
            )
            created += 1

        messages.success(request, f'已导入 {created} 个提示词预设')
        return redirect('preset_list')

    return render(request, 'dashboard/preset_upload.html', {})


@staff_required
def preset_delete(request, pid):
    preset = get_object_or_404(PromptPreset, id=pid)
    product_count = preset.products.count()
    if product_count > 0:
        messages.error(request, f'「{preset.name}」下有 {product_count} 个产品，请先删除产品再删除预设')
        return redirect('preset_list')
    # 删除关联的 .md 文件
    if preset.md_file:
        try:
            fp = Path(str(preset.md_file.path))
            if fp.exists():
                fp.unlink()
        except Exception:
            pass
    preset.delete()
    messages.success(request, f'已删除「{preset.name}」')
    return redirect('preset_list')


@staff_required
def preset_batch_delete(request):
    ids = request.GET.getlist('ids')
    ids = [int(i) for i in ids if i.isdigit()]
    deleted, blocked = [], []
    for pid in ids:
        try:
            preset = PromptPreset.objects.get(id=pid)
            if preset.products.count() > 0:
                blocked.append(preset.name)
            else:
                if preset.md_file:
                    try:
                        fp = Path(str(preset.md_file.path))
                        if fp.exists():
                            fp.unlink()
                    except Exception:
                        pass  # 文件不存在或路径无效
                preset.delete()
                deleted.append(preset.name)
        except PromptPreset.DoesNotExist:
            pass
    if deleted:
        messages.success(request, f'已删除 {len(deleted)} 个预设')
    if blocked:
        messages.error(request, f'以下预设有关联产品无法删除：{", ".join(blocked)}')
    return redirect('preset_list')


@staff_required
def preset_edit(request, pid):
    preset = get_object_or_404(PromptPreset, id=pid)
    if request.method == 'POST':
        preset.name = request.POST.get('name', preset.name)
        content = _normalize_preset_prompt(request.POST.get('content', preset.content))  # V7: 替换遗留占位符
        content, _warnings = _normalize_risky_keywords(content)  # V7.1: 标准化高风险词
        preset.content = content
        preset.negative_prompt = request.POST.get('negative_prompt', preset.negative_prompt)
        preset.is_active = request.POST.get('is_active') == 'on'
        preset.save()
        messages.success(request, '已更新')
        return redirect('preset_list')
    return render(request, 'dashboard/preset_edit.html', {'preset': preset})


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
        '你是商品图背景分析器。\n'
        '只分析:\n'
        '  - background_type\n'
        '  - background_elements\n'
        '  - lighting_type\n'
        '  - color_palette\n\n'
        '禁止输出:\n'
        '  person, people, model, woman, man, fashion, editorial,\n'
        '  clothing, product, tshirt, hoodie, garment, fabric,\n'
        '  composition, shot type, camera, lens, photography style\n\n'
        'For each distinct print design style, output JSON:\n'
        '[{\n'
        '  "name": "Category Name (Chinese + English)",\n'
        '  "keywords": ["kw1","kw2",...],\n'
        '  "print_prompt": "describe ONLY the PRINT/GRAPHIC design — theme, art style, color palette, technique",\n'
        '  "style_json": {\n'
        '    "background_type": "indoor",\n'
        '    "background_elements": ["green_plant","wood_desk"],\n'
        '    "lighting_type": "soft",\n'
        '    "color_palette": ["beige","green"]\n'
        '  },\n'
        '  "extra_prompt": ""\n'
        '}]\n\n'
        'PRINT_PROMPT RULES:\n'
        '- Describe ONLY the print design: theme, art style, graphic elements, color palette, technique\n'
        '- Forbidden: garment, fabric, clothing color, background, scene, lighting, model, human, tshirt, hoodie\n'
        '- Example: "bold graffiti typography, street art style, black and white high-contrast ink, distressed texture, urban aesthetic"\n\n'
        'STYLE_JSON RULES (V5.2 WHITELIST — ONLY these 4 keys):\n'
        '- background_type: indoor, outdoor, studio, undefined\n'
        '- background_elements: array of objects in scene (max 5 items, use underscores for spaces)\n'
        '- lighting_type: soft, hard, natural, studio, warm, cool\n'
        '- color_palette: 2-5 environmental colors (NOT garment/clothing colors)\n'
        '- NEVER include any other keys in style_json\n'
        '- style_json describes ONLY the environment, NOT the product\n\n'
        'Keywords: mix of Chinese and English for searchability.'
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
    """创建分类 .md 文件 — V5.2 白名单 JSON + 优先级体系"""
    md = f"""# {category.name}

## 匹配关键词
{category.keywords}

---
## V5.2 Prompt 架构（白名单 JSON Sanitizer）

### Priority 1: PRODUCT_IDENTITY（模板提供，LOCKED）
{{{{template_prompt}}}}
lock_color: true, lock_fit: true, lock_product_category: true, lock_print_placement: true

### Priority 2: PRINT_ARTWORK（印花设计）
{category.print_prompt}

### Priority 3: STYLE_CONTEXT（白名单净化：仅 background_type + background_elements + lighting_type + color_palette）
{category.style_context or '{{{{background}}}}, soft lighting, clean product presentation'}

### TEMPLATE BINDING
- PRODUCT_IDENTITY always wins over STYLE_CONTEXT
- Garment color, fit, neckline, sleeve are LOCKED
- STYLE_CONTEXT describes ONLY environment (no composition, no shot type, no camera)

### V5.2 PRODUCT ONLY MODE
single apparel product photo,
t-shirt mockup,
flat lay or ghost mannequin,
clean ecommerce product presentation,
no humans, no models, no faces, no hands, no bodies

---
## 负面 Prompt
low quality, blurry, anime, cartoon, childish, cute style, plastic fabric,
polyester texture, oversaturated, bad anatomy, deformed clothing,
cropped garment, watermark, logo distortion, low resolution,
human, person, people, man, woman, model, fashion model,
portrait, face, head, arms, hands, legs, body,
editorial, street photography, lifestyle photography,
floating artwork, floating print, standalone artwork, poster, canvas,
framed picture, art print, print on wall, isolated graphic, detached print,
text overlay, border, decorative frame, mockup background,
blank t-shirt, plain t-shirt
"""
    CATEGORY_MD_DIR.mkdir(parents=True, exist_ok=True)
    filepath = CATEGORY_MD_DIR / f'{category.slug}.md'
    filepath.write_text(md, encoding='utf-8')
    category.prompt_file = str(filepath.relative_to(PROJECT_ROOT))
    category.negative_prompt = (
        'low quality, blurry, anime, cartoon, childish, cute style, '
        'plastic fabric, polyester texture, oversaturated, '
        'bad anatomy, deformed clothing, cropped garment, '
        'watermark, logo distortion, low resolution, '
        'human, person, people, man, woman, model, fashion model, '
        'portrait, face, head, arms, hands, legs, body, '
        'editorial, street photography, lifestyle photography, '
        'floating artwork, floating print, standalone artwork, '
        'poster, canvas, framed picture, art print, '
        'print on wall, print on paper, isolated graphic, '
        'detached print, text overlay, border, decorative frame, '
        'mockup background, blank t-shirt, plain t-shirt'
    )
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
    products = Product.objects.prefetch_related('skus__template').select_related('country', 'category', 'prompt_preset').order_by('-created_at')
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
    presets = PromptPreset.objects.filter(is_active=True)
    print_presets = PrintDesignPreset.objects.filter(is_active=True)
    pod_templates = TShirtTemplate.objects.filter(is_active=True, is_pod_template=True)
    countries = Country.objects.all()
    mode = request.GET.get('mode', 'direct')

    if request.method == 'POST':
        mode = request.POST.get('mode', 'direct')
        country_code = request.POST.get('country')
        count = int(request.POST.get('count', 1))

        if not country_code:
            messages.error(request, '请选择国家')
            return redirect('product_create')

        country = get_object_or_404(Country, code=country_code)

        if mode == 'pod':
            # POD 模式
            print_preset_ids = request.POST.getlist('print_preset')
            template_id = request.POST.get('template')
            if not print_preset_ids:
                messages.error(request, '请选择至少一个印花分类')
                return redirect(f'{request.path}?mode=pod')
            if not template_id:
                messages.error(request, '请选择 POD 模板')
                return redirect(f'{request.path}?mode=pod')

            try:
                pod_template = TShirtTemplate.objects.get(id=int(template_id), is_active=True, is_pod_template=True)
            except (ValueError, TShirtTemplate.DoesNotExist):
                messages.error(request, '无效的 POD 模板')
                return redirect(f'{request.path}?mode=pod')

            total = 0
            for ppid in print_preset_ids:
                try:
                    pp = PrintDesignPreset.objects.get(id=int(ppid), is_active=True)
                except (ValueError, PrintDesignPreset.DoesNotExist):
                    continue
                for i in range(count):
                    product = Product.objects.create(
                        country=country, generation_mode='pod',
                        template=pod_template,
                        size_info='XS,S,M,L,XL,XXL,3XL,4XL', status='processing'
                    )
                    threading.Thread(target=_run_pod_generation, args=(product.id, pp.id), daemon=True).start()
                    total += 1
            messages.success(request, f'创建 {total} 个 POD 产品，正在生成...')
            return redirect('product_list')
        else:
            # Direct 模式（原 V7 逻辑）
            preset_ids = request.POST.getlist('preset')
            if not preset_ids:
                messages.error(request, '请选择至少一个分类')
                return redirect('product_create')

            total = 0
            for pid in preset_ids:
                try:
                    preset = PromptPreset.objects.get(id=int(pid), is_active=True)
                except (ValueError, PromptPreset.DoesNotExist):
                    continue
                for i in range(count):
                    product = Product.objects.create(
                        country=country, prompt_preset=preset, generation_mode='direct',
                        size_info='XS,S,M,L,XL,XXL,3XL,4XL', status='processing'
                    )
                    threading.Thread(target=_run_preset_generation, args=(product.id,), daemon=True).start()
                    total += 1
            messages.success(request, f'创建 {total} 个产品（{len(preset_ids)} 个分类），正在生成...')
            return redirect('product_list')

    # V7: 按颜色分组
    white_presets = [p for p in presets if p.shirt_color == 'white']
    black_presets = [p for p in presets if p.shirt_color == 'black']
    other_presets = [p for p in presets if p.shirt_color not in ('white', 'black')]
    # POD 分组
    white_print = [p for p in print_presets if p.shirt_color == 'white']
    black_print = [p for p in print_presets if p.shirt_color == 'black']
    other_print = [p for p in print_presets if p.shirt_color not in ('white', 'black')]
    return render(request, 'dashboard/product_create.html', {
        'presets': presets, 'countries': countries, 'mode': mode,
        'white_presets': white_presets, 'black_presets': black_presets, 'other_presets': other_presets,
        'print_presets': print_presets, 'pod_templates': pod_templates,
        'white_print': white_print, 'black_print': black_print, 'other_print': other_print,
    })


@staff_required
def preset_classify(request):
    """V7: 上传印花参考图 → Doubao AI 自动匹配分类"""
    from django.http import JsonResponse
    if request.method != 'POST' or not request.FILES.get('image'):
        return JsonResponse({'error': 'No image'}, status=400)

    try:
        image_data = request.FILES['image'].read()
        presets = list(PromptPreset.objects.filter(is_active=True))
        preset_names = [p.name for p in presets]

        if not preset_names:
            return JsonResponse({'error': 'No presets available'}, status=400)

        import base64
        img_b64 = base64.b64encode(image_data).decode()
        names_list = '\n'.join(preset_names)
        resp = requests.post(
            f'{settings.DEEPSEEK_BASE_URL}/chat/completions',
            headers={'Authorization': f'Bearer {settings.DEEPSEEK_API_KEY}', 'Content-Type': 'application/json'},
            json={'model': 'doubao-seed-2.0-lite', 'messages': [{'role': 'user', 'content': [
                {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{img_b64}'}},
                {'type': 'text', 'text': (
                    f'This is a print design on a garment. Which category does it best match?\n'
                    f'Available categories:\n{names_list}\n\n'
                    f'Output ONLY the EXACT category name, no other text.'
                )}
            ]}], 'max_tokens': 50}, timeout=30)
        resp.raise_for_status()
        matched_name = resp.json()['choices'][0]['message']['content'].strip()

        # Find matching preset
        matched = None
        for p in presets:
            if p.name.lower() == matched_name.lower():
                matched = p
                break
        # Fuzzy match
        if not matched:
            for p in presets:
                if matched_name.lower() in p.name.lower() or p.name.lower() in matched_name.lower():
                    matched = p
                    break

        return JsonResponse({
            'matched_name': matched_name,
            'preset_id': matched.id if matched else None,
            'preset_name': matched.name if matched else None,
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@staff_required
def product_edit(request, pid):
    p = get_object_or_404(Product.objects.prefetch_related('skus__template').select_related('category', 'country', 'prompt_preset'), id=pid)
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
def product_batch_regenerate(request):
    ids = request.GET.getlist('ids')
    ids = [int(i) for i in ids if i.isdigit()]
    if ids:
        products = Product.objects.filter(id__in=ids)
        for p in products:
            p.status = 'processing'; p.save()
            if p.prompt_preset:
                threading.Thread(target=_run_preset_generation, args=(p.id,), daemon=True).start()
            else:
                threading.Thread(target=_run_generation_v2, args=(p.id, 0), daemon=True).start()
        messages.success(request, f'已启动 {len(ids)} 个产品的重新生成')
    return redirect('product_list')

@staff_required
def product_generate_all(request):
    products = Product.objects.filter(status__in=['pending'])
    for p in products:
        p.status = 'processing'; p.save()
        if p.prompt_preset:
            threading.Thread(target=_run_preset_generation, args=(p.id,), daemon=True).start()
        else:
            threading.Thread(target=_run_generation_v2, args=(p.id, 0), daemon=True).start()
    messages.success(request, f'已启动 {products.count()} 个产品的生成')
    return redirect('product_list')

@staff_required
def product_regenerate(request, pid):
    p = get_object_or_404(Product, id=pid)
    p.status = 'processing'; p.save()
    if p.prompt_preset:
        threading.Thread(target=_run_preset_generation, args=(p.id,), daemon=True).start()
    else:
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
# ============================================================
# V6 Prompt Composer
# ============================================================
def _load_template_json(template_key: str) -> dict:
    """加载产品模板 JSON"""
    fp = TEMPLATE_DIR / f'{template_key}.json'
    if not fp.exists():
        raise FileNotFoundError(f'Template not found: {fp}')
    return json.loads(fp.read_text(encoding='utf-8'))


def _template_to_text(tmpl: dict) -> str:
    """V6: JSON 模板 → 自然语言"""
    ptype = tmpl.get('product_type', 'tshirt')
    color = tmpl.get('color', 'white')
    fit = tmpl.get('fit', 'regular')
    neck = tmpl.get('neck', 'crew neck')
    sleeve = tmpl.get('sleeve', 'short sleeve')
    ptype_display = ptype.replace('tshirt', 't-shirt').replace('tanktop', 'tank top')
    return (
        f'{color} cotton {ptype_display},\n'
        f'{neck},\n'
        f'{sleeve},\n'
        f'{fit} fit,\n'
        f'real fabric texture,\n'
        f'natural folds,\n'
        f'large printable area,\n'
        f'apparel product photography,\n'
        f'taobao clothing listing photo,\n'
        f'wooden hanger,\n'
        f'closet background,\n'
        f'warm indoor lighting'
    )


def _wrap_artwork(artwork_description: str) -> str:
    """V6: 将印花描述包装在服装印花指令中"""
    return (
        f'A graphic print is applied on the center chest area.\n'
        f'The graphic shows:\n'
        f'{artwork_description}\n'
        f'The graphic is printed on fabric.\n'
        f'The graphic follows fabric folds.\n'
        f'The graphic is not floating.\n'
        f'The graphic is not detached.'
    )


def _compose_v6_prompt(template_key: str, artwork_description: str) -> str:
    """V6: SYSTEM_PROMPT + TEMPLATE + ARTWORK"""
    tmpl = _load_template_json(template_key)
    return (
        SYSTEM_PROMPT + '\n\n'
        + _template_to_text(tmpl) + '\n\n'
        + _wrap_artwork(artwork_description)
    )


def _run_preset_generation(product_id):
    """V7: .md → ComfyUI 4图 → CLIP评分 → Validator → 综合排序 → 输出Top1"""
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    product = Product.objects.select_related('prompt_preset', 'country').get(id=product_id)
    preset = product.prompt_preset
    if not preset:
        Product.objects.filter(id=product_id).update(status='failed', error_message='No preset')
        return

    rng = random.Random(product_id * 1000)
    base_seed = rng.randint(1, 999999999)
    product.seed = base_seed
    product.save()

    # V7: 解析 .md → positive/negative，去标题 + 替换占位符兜底
    positive, negative = _parse_md_prompt(preset.content)
    if not positive:
        positive = preset.content
    positive = _normalize_preset_prompt(positive)  # 兜底：防止数据库已有旧占位符
    positive, _warnings = _normalize_risky_keywords(positive)  # V7.1: 标准化高风险词
    positive = _apply_shirt_color_lock(positive, preset.shirt_color)  # V7: 颜色锁定兜底
    positive = _apply_print_placement_lock(positive, preset.shirt_color)  # V7.1: 纯色+胸口限制
    positive = _apply_flat_print_lock(positive)  # V7.1: 禁止口袋/刺绣/3D
    neg = negative or V6_NEGATIVE_PROMPT

    print(f'\n{"="*60}')
    print(f'V7 Product#{product_id} | Category: {preset.name} | Base Seed: {base_seed}')
    print(f'{"="*60}')
    print(positive)
    print(f'{"-"*60}')
    print(f'NEGATIVE: {neg}')
    print(f'{"="*60}\n')

    provider = ComfyUIProvider()

    # Step 1: 生成 4 张候选图（间隔 2s 防 ComfyUI 过载）
    images = []
    errors = []
    for idx in range(4):
        seed = base_seed + idx
        if idx > 0:
            time.sleep(2)  # 避免同时压 4 个请求到 ComfyUI
        try:
            result = provider.generate_image(prompt=positive, params={
                'seed': seed, 'steps': 28, 'cfg_scale': 5.5,
                'width': 1024, 'height': 1024,
                'negative_prompt': neg,
            })
            if result.images:
                images.append({'img': result.images[0], 'seed': seed, 'idx': idx})
                print(f'  -> Image {idx+1}/4 OK (seed={seed})')
            else:
                errors.append(f'Image{idx+1}: no image returned')
                print(f'  -> Image {idx+1}/4 EMPTY (seed={seed})')
        except Exception as e:
            err_msg = str(e)[:100]
            errors.append(f'Image{idx+1}: {err_msg}')
            print(f'  -> Image {idx+1}/4 FAILED: {e}')

    if not images:
        err_detail = '; '.join(errors) if errors else 'All 4 returned no images'
        Product.objects.filter(id=product_id).update(status='failed', error_message=err_detail[:500])
        return

    # Step 2: CLIP 评分 + Validator
    print(f'\n{"="*60}')
    print(f'CLIP Scoring + Validation...')
    print(f'{"="*60}')
    try:
        from apps.generation.clip_scorer import ClipScorer
        scorer = ClipScorer()
        for item in images:
            result = scorer.evaluate(item['img'], positive)
            item['score'] = result
            v = result['details']
            print(f'  Image#{item["idx"]+1} seed={item["seed"]}: '
                  f'CLIP={result["clip_score"]} combined={result["combined_score"]} '
                  f'validators={result["validator_pass"]}/4 '
                  f'[G:{v["garment"][0]} P:{v["print"][0]} H:{v["no_human"][0]} PP:{v["product_photo"][0]}]')
    except Exception as e:
        print(f'  CLIP scoring failed: {e}, using order-based selection')
        # Fallback: use first image
        for item in images:
            item['score'] = {'combined_score': 100 - item['idx'] * 10, 'clip_score': 0, 'validator_pass': 0}

    # Step 3: 综合排序 → Top 1
    images.sort(key=lambda x: x['score']['combined_score'], reverse=True)
    best = images[0]
    print(f'  >>> Best: Image#{best["idx"]+1} seed={best["seed"]} score={best["score"]["combined_score"]}')

    # Step 4: 清理旧 SKU，保存所有 4 张为新 SKU
    ProductSKU.objects.filter(product_id=product_id).delete()
    for item in images:
        img = item['img']
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=92)
        buf.seek(0)
        sku = ProductSKU.objects.create(product=product)
        sku.mockup_image.save(f'p{product_id}_v{item["idx"]}.jpg', ContentFile(buf.getvalue()), save=True)

    # 将最佳图片的 URL 也存到产品（用第一张 SKU）
    print(f'  Best image score: {best["score"]["combined_score"]}, validators: {best["score"]["validator_pass"]}/4')

    # Text generation
    try:
        _generate_text_v2(product_id)
        Product.objects.filter(id=product_id).update(status='completed')
    except Exception as e:
        import traceback
        Product.objects.filter(id=product_id).update(status='text_pending', error_message=str(e)[:500])
        print(f'Text gen failed for {product_id}: {e}\n{traceback.format_exc()}')


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
            neg = getattr(category, 'negative_prompt', '') or (
                'low quality, blurry, anime, cartoon, childish, cute style, '
                'plastic fabric, polyester texture, oversaturated, '
                'bad anatomy, deformed clothing, cropped garment, '
                'watermark, logo distortion, low resolution, '
                'human, person, people, man, woman, model, fashion model, '
                'portrait, face, head, arms, hands, legs, body, '
                'editorial, street photography, lifestyle photography, '
                'floating artwork, floating print, standalone artwork, '
                'poster, canvas, framed picture, art print, '
                'print on wall, print on paper, isolated graphic, '
                'detached print, text overlay, border, decorative frame, '
                'mockup background, blank t-shirt, plain t-shirt'
            )
            print(f'\n{"="*60}')
            print(f'Product#{product_id} SKU#{sku.id} | Template: {sku.template.name} ({sku.template.color})')
            print(f'{"="*60}')
            print(prompt)
            print(f'{"-"*60}')
            print(f'NEGATIVE: {neg}')
            print(f'{"="*60}\n')

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
    """V5.1 优先级体系: PRODUCT_IDENTITY > PRINT_ARTWORK > STYLE_CONTEXT"""
    # Priority 1 (HIGHEST): PRODUCT_IDENTITY — LOCKED, 不可覆盖
    raw_identity = template.prompt_body or ''
    if raw_identity:
        # V5.2: 运行时 sanitize 旧数据（兼容各种格式）
        product_identity = _sanitize_product_identity(raw_identity)
        # 清理旧数据残留的双逗号
        product_identity = product_identity.replace(',,', ',').replace(',\n,', ',')
    else:
        product_identity = (
            f'solid {template.color} t-shirt,\n'
            'oversized fit,\ncrew neck,\nshort sleeve,\nheavyweight cotton,\n'
            '230gsm fabric,\ncenter chest graphic print,\n'
            'realistic cotton texture,\nnatural fabric folds,\n'
            'lock_color: true,\nlock_fit: true,\n'
            'lock_product_category: true,\nlock_print_placement: true'
        )
    # 小修正
    product_identity = product_identity.replace('tshirt', 't-shirt')
    # 确保模板颜色在 prompt 中
    if template.color.lower() not in product_identity.lower():
        product_identity = f'solid {template.color} t-shirt,\n' + product_identity

    # Priority 2: PRINT_ARTWORK — 仅印花，不影响服装
    print_artwork = category.print_prompt or 'stylish graphic print design'

    # Priority 3 (LOWEST): STYLE_CONTEXT — 仅环境，运行时 sanitize 保底
    raw_style = getattr(category, 'style_context', '') or (
        f'{background},\nsoft daylight,\ncommercial product photography,\n'
        '85mm lens,\nclean product presentation'
    )
    style_context = _sanitize_style_context(raw_style)

    # V5.1 TEMPLATE BINDING — 强制模板绑定 + 禁止人物
    template_binding = (
        'TEMPLATE BINDING — STRICT:\n'
        f'- Garment color is LOCKED: {template.color}\n'
        '- Garment category, fit, neckline, sleeve are LOCKED\n'
        '- Print placement is LOCKED to center chest area\n'
        '- STYLE_CONTEXT describes ONLY the environment (background + lighting + composition)\n'
        '- STYLE_CONTEXT must NOT override PRODUCT_IDENTITY\n'
        '- PRODUCT_IDENTITY always wins over STYLE_CONTEXT'
    )

    # V5.2 PRODUCT ONLY MODE
    product_only = (
        'PRODUCT ONLY MODE:\n'
        'single apparel product photo,\n'
        't-shirt mockup,\n'
        'flat lay or ghost mannequin,\n'
        'clean ecommerce product presentation,\n'
        'no humans, no models, no faces, no hands, no bodies\n'
        '- The t-shirt is the ONLY subject in the image\n'
        '- No street photography, no lifestyle, no editorial\n'
        '- Generate a clean ecommerce product image'
    )

    return (
        f'[PRODUCT_IDENTITY — PRIORITY 1]\n{product_identity}\n\n'
        f'[PRINT_ARTWORK — PRIORITY 2]\n{print_artwork}\n\n'
        f'[STYLE_CONTEXT — PRIORITY 3 (environment only)]\n{style_context}\n\n'
        f'{template_binding}\n\n'
        f'{product_only}'
    )

def _run_pod_generation(product_id, print_preset_id):
    """POD 模式: 生成印花 → 去背景 → 合成到模板 → 保存 SKU"""
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    product = Product.objects.select_related('template', 'country').get(id=product_id)
    pp = PrintDesignPreset.objects.get(id=print_preset_id)
    template = product.template

    if not template or not template.is_pod_template:
        Product.objects.filter(id=product_id).update(status='failed', error_message='No POD template')
        return
    if not all([template.print_area_x is not None, template.print_area_y is not None,
                template.print_area_width, template.print_area_height]):
        Product.objects.filter(id=product_id).update(status='failed', error_message='Template missing print area')
        return

    rng = random.Random(product_id * 1000 + print_preset_id)
    base_seed = rng.randint(1, 999999999)
    provider = ComfyUIProvider()

    # Step 1: 生成随机印花 prompt
    from apps.generation.print_variants import build_random_print_prompt
    positive, negative, meta = build_random_print_prompt(pp, seed=base_seed)

    print(f'\n{"="*60}')
    print(f'POD Product#{product_id} | PrintPreset: {pp.name} | Seed: {base_seed}')
    print(f'Variation: {meta["palette"]} | {meta["composition"]} | {meta["elements"]}')
    print(f'{"="*60}')

    # Step 2: ComfyUI 生成印花
    try:
        result = provider.generate_print_design(positive, params={
            'seed': base_seed, 'negative_prompt': negative,
        })
        if not result.images:
            Product.objects.filter(id=product_id).update(status='failed', error_message='Print design generation returned no image')
            return
        print_image = result.images[0]
    except Exception as e:
        Product.objects.filter(id=product_id).update(status='failed', error_message=f'Print gen failed: {str(e)[:200]}')
        return

    # Step 3: 保存原始印花
    buf = io.BytesIO()
    print_image.save(buf, format='PNG')
    buf.seek(0)
    print_design = PrintDesign.objects.create(
        preset=pp, shirt_color=pp.shirt_color,
        prompt=positive, negative_prompt=negative,
        variation_metadata=meta, seed=base_seed,
    )
    print_design.raw_image.save(f'p{product_id}_print.png', ContentFile(buf.getvalue()), save=True)
    product.print_design = print_design
    product.save()

    # Step 4: 去背景
    try:
        bg_result = provider.remove_print_background(print_image)
        transparent = bg_result.images[0] if bg_result.images else print_image
        if bg_result.metadata.get('warning'):
            print(f'  WARNING: {bg_result.metadata["warning"]}')
    except Exception:
        transparent = print_image

    buf2 = io.BytesIO()
    transparent.save(buf2, format='PNG')
    buf2.seek(0)
    print_design.transparent_image.save(f'p{product_id}_print_trans.png', ContentFile(buf2.getvalue()), save=True)

    # Step 5: 合成到模板
    try:
        template_img = Image.open(template.image.path)
        # Resize print to match print area
        composite_result = provider.composite_pod_image(
            template_img, transparent,
            x=template.print_area_x, y=template.print_area_y,
            width=template.print_area_width, height=template.print_area_height,
        )
        if not composite_result.images:
            Product.objects.filter(id=product_id).update(status='failed', error_message='Composite returned no image')
            return
        final_image = composite_result.images[0]
    except Exception as e:
        Product.objects.filter(id=product_id).update(status='failed', error_message=f'Composite failed: {str(e)[:200]}')
        return

    # Step 6: 保存最终 SKU
    ProductSKU.objects.filter(product_id=product_id).delete()
    buf3 = io.BytesIO()
    final_image.save(buf3, format='JPEG', quality=92)
    buf3.seek(0)
    sku = ProductSKU.objects.create(product=product)
    sku.mockup_image.save(f'p{product_id}_pod.jpg', ContentFile(buf3.getvalue()), save=True)

    Product.objects.filter(id=product_id).update(status='completed', seed=base_seed)
    print(f'POD Product#{product_id} completed')


def _generate_text_v2(product_id):
    """用 DeepSeek 生成商品标题和描述"""
    from apps.generation.deepseek import DeepSeekProvider
    from ai.prompts.loader import build_text_prompt
    product = Product.objects.select_related('country', 'category', 'prompt_preset').get(id=product_id)
    language_map = {'ID': 'id', 'TH': 'th'}
    language = language_map.get(product.country.code, 'id')
    # V7 preset mode or legacy category mode
    if product.prompt_preset:
        desc = product.prompt_preset.content[:100]
    elif product.category and product.category.print_prompt:
        desc = product.category.print_prompt[:100]
    else:
        desc = 'stylish print design'
    prompt = build_text_prompt(language=language, print_description=desc)
    provider = DeepSeekProvider()
    result = provider.generate_text(prompt, language=language)
    product.title = result.title
    product.description = result.description
    product.save()

# Import at bottom to avoid circular
from apps.generation.comfyui import ComfyUIProvider

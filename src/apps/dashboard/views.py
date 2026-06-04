"""运营面板视图 — 完整 CRUD + AI 生成 + SKU 支持"""
import json, io, threading, sys, os
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

    config_path = PROJECT_ROOT / 'data' / 'config.json'
    variant_count = 4
    try:
        if config_path.exists():
            with open(config_path) as f:
                data = json.load(f)
            variant_count = data.get('variant_count', 4)
    except Exception:
        pass

    if request.method == 'POST':
        selected_model = request.POST.get('model', current_model)
        variant_count = int(request.POST.get('variant_count', 4))
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w') as f:
            json.dump({'comfyui_model': selected_model, 'variant_count': variant_count}, f)
        messages.success(request, f'已切换模型: {selected_model}')
        return redirect('settings_page')

    return render(request, 'dashboard/settings.html', {
        'models': models, 'current_model': current_model, 'variant_count': variant_count,
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
            TShirtTemplate.objects.create(name=name, color=color, image=image)
            messages.success(request, '模板上传成功')
            return redirect('template_list')
    return render(request, 'dashboard/template_upload.html')


@staff_required
def template_edit(request, tid):
    t = get_object_or_404(TShirtTemplate, id=tid)
    if request.method == 'POST':
        t.name = request.POST.get('name', t.name)
        t.color = request.POST.get('color', t.color)
        if request.FILES.get('image'): t.image = request.FILES['image']
        t.is_active = request.POST.get('is_active') == 'on'; t.save()
        messages.success(request, '已更新')
        return redirect('template_list')
    return render(request, 'dashboard/template_edit.html', {'template': t})


@staff_required
def template_delete(request, tid):
    get_object_or_404(TShirtTemplate, id=tid).update(is_active=False) if False else get_object_or_404(TShirtTemplate, id=tid).__setattr__('is_active', False) or get_object_or_404(TShirtTemplate, id=tid).save()
    t = get_object_or_404(TShirtTemplate, id=tid); t.is_active = False; t.save()
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
        action = request.POST.get('action', 'create')

        if not pattern_ids or not country_code or not template_ids:
            messages.error(request, '请选择印花、国家和至少一个模板')
            return redirect('product_create')

        country = get_object_or_404(Country, code=country_code)
        created = 0
        for pid in pattern_ids:
            pattern = get_object_or_404(Pattern, id=int(pid))
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
                                 args=(pattern.id, product.id, pattern.source_type == 'clean_print'),
                                 daemon=True).start()

        messages.success(request, f'创建 {created} 个产品（每个 {len(template_ids)} 个SKU），正在生成中...')
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

def _run_pipeline_sync(pattern_id, product_id, skip_preprocess):
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

        # Step 2: 图像生成 — 只生成印花
        try:
            from celery_app.image_gen import generate_print_variants_task
            generate_print_variants_task(pattern_id, product_id, variant_count=_get_variant_count())
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


def _get_variant_count():
    try:
        config_path = PROJECT_ROOT / 'data' / 'config.json'
        if config_path.exists():
            with open(config_path) as f:
                return json.load(f).get('variant_count', 4)
    except Exception:
        pass
    return 4


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

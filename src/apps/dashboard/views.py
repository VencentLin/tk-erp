"""运营面板视图 — 完整 CRUD + AI 生成"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import HttpResponse
from django.db.models import Count

from apps.patterns.models import Pattern
from apps.templates_app.models import TShirtTemplate
from apps.products.models import Product
from apps.core.models import Country, Store
from apps.patterns.batch_import import batch_import_patterns

staff_required = user_passes_test(lambda u: u.is_staff, login_url='/admin/login/')


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
        'recent_products': Product.objects.order_by('-created_at')[:8],
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
    return render(request, 'dashboard/country_list.html', {
        'countries': countries, 'stores': stores
    })


@staff_required
def country_save(request):
    if request.method == 'POST':
        cid = request.POST.get('id')
        code = request.POST.get('code', '').strip().upper()
        name = request.POST.get('name', '').strip()
        if code and name:
            if cid:
                c = get_object_or_404(Country, id=int(cid))
                c.code, c.name = code, name
                c.save()
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
                s = get_object_or_404(Store, id=int(sid))
                s.name, s.country, s.owner = name, country, request.user
                s.save()
            else:
                Store.objects.create(name=name, country=country, owner=request.user)
    return redirect('country_list')


@staff_required
def store_delete(request, sid):
    Store.objects.filter(id=sid).delete()
    return redirect('country_list')


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
        source_type = request.POST.get('source_type', 'clean_print')
        note = request.POST.get('note', '')
        for f in files:
            if f.size > 0:
                Pattern.objects.create(image=f, uploaded_by=request.user,
                                       source_type=source_type, note=note or f.name)
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
    p.is_deleted = True
    p.save()
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
                files=uploaded_files if uploaded_files else None,
                excel_file=excel_data, uploaded_by=request.user,
            )
            ctx.update(results=results, new_count=sum(1 for r in results if r.status == 'new'),
                       dup_count=sum(1 for r in results if r.status == 'duplicate'),
                       err_count=sum(1 for r in results if r.status == 'error'))
            messages.success(request,
                f'导入完成: {ctx["new_count"]} 新增, {ctx["dup_count"]} 重复, {ctx["err_count"]} 失败')
        except Exception as e:
            import traceback
            ctx['error'] = f'{type(e).__name__}: {e}\n{traceback.format_exc()}'
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
        if request.FILES.get('image'):
            t.image = request.FILES['image']
        t.is_active = request.POST.get('is_active') == 'on'
        t.save()
        messages.success(request, '已更新')
        return redirect('template_list')
    return render(request, 'dashboard/template_edit.html', {'template': t})


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
    products = Product.objects.select_related('country', 'pattern', 'template').order_by('-created_at')
    if country_code:
        products = products.filter(country__code=country_code)
    if status:
        products = products.filter(status=status)
    return render(request, 'dashboard/product_list.html', {
        'products': products,
        'countries': Country.objects.all(),
        'statuses': Product.STATUS_CHOICES,
        'selected_country': country_code,
        'selected_status': status,
    })


@staff_required
def product_create(request):
    """创建产品并触发生成"""
    patterns = Pattern.objects.filter(is_deleted=False).order_by('-created_at')
    templates = TShirtTemplate.objects.filter(is_active=True)
    countries = Country.objects.all()

    if request.method == 'POST':
        pattern_ids = request.POST.getlist('patterns')
        country_code = request.POST.get('country')
        template_id = request.POST.get('template')
        action = request.POST.get('action', 'create')

        if not pattern_ids or not country_code or not template_id:
            messages.error(request, '请选择印花、国家和模板')
            return redirect('product_create')

        country = get_object_or_404(Country, code=country_code)
        template = get_object_or_404(TShirtTemplate, id=int(template_id))

        created = 0
        for pid in pattern_ids:
            pattern = get_object_or_404(Pattern, id=int(pid))
            product = Product.objects.create(
                country=country, pattern=pattern, template=template,
                status='processing' if action == 'generate' else 'pending'
            )
            created += 1

            if action == 'generate':
                # 同步执行生成流水线（无需 Celery/Redis）
                import threading
                t = threading.Thread(
                    target=_run_pipeline_sync,
                    args=(pattern.id, [product.id], pattern.source_type == 'clean_print'),
                    daemon=True
                )
                t.start()

        msg = f'创建 {created} 个产品'
        if action == 'generate':
            msg += '，正在后台生成中...'
        messages.success(request, msg)
        return redirect('product_list')

    return render(request, 'dashboard/product_create.html', {
        'patterns': patterns, 'templates': templates, 'countries': countries,
    })


def _run_pipeline_sync(pattern_id, product_ids, skip_preprocess):
    """同步执行生成流水线（后台线程）"""
    from apps.patterns.models import Pattern
    from apps.products.models import Product
    import io
    from PIL import Image

    try:
        # Step 1: 预处理（抠图）
        if not skip_preprocess:
            try:
                from celery_app.preprocessing import remove_background_task
                remove_background_task(pattern_id)
            except Exception as e:
                print(f'Preprocessing failed: {e}')

        # Step 2: 图像生成
        for pid in product_ids:
            try:
                from celery_app.image_gen import generate_print_variants_task
                generate_print_variants_task(pattern_id, pid, variant_count=4)
            except Exception as e:
                Product.objects.filter(id=pid).update(status='failed', error_message=str(e))
                print(f'Image gen failed for product {pid}: {e}')

        # Step 3: 文本生成
        for pid in product_ids:
            try:
                from celery_app.text_gen import generate_product_text_task
                generate_product_text_task(pid)
            except Exception as e:
                Product.objects.filter(id=pid).update(status='text_pending', error_message=str(e))
                print(f'Text gen failed for product {pid}: {e}')

    except Exception as e:
        Product.objects.filter(id__in=product_ids).update(status='failed', error_message=str(e))


@staff_required
def product_edit(request, pid):
    p = get_object_or_404(Product, id=pid)
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
    """批量生成所有待处理产品"""
    products = Product.objects.filter(status__in=['pending', 'text_pending']).select_related('pattern')
    import threading
    for p in products:
        p.status = 'processing'
        p.save()
        t = threading.Thread(
            target=_run_pipeline_sync,
            args=(p.pattern_id, [p.id], p.pattern.source_type == 'clean_print'),
            daemon=True
        )
        t.start()
    messages.success(request, f'已启动 {products.count()} 个产品的生成')
    return redirect('product_list')


@staff_required
def product_regenerate(request, pid):
    """重新触发生成"""
    p = get_object_or_404(Product, id=pid)
    import threading
    p.status = 'processing'
    p.save()
    t = threading.Thread(
        target=_run_pipeline_sync,
        args=(p.pattern_id, [p.id], p.pattern.source_type == 'clean_print'),
        daemon=True
    )
    t.start()
    messages.success(request, '正在后台生成中...')
    return redirect('product_list')


@staff_required
def product_export(request):
    ids = request.GET.getlist('ids')
    if not ids:
        messages.error(request, '请先选择产品')
        return redirect('product_list')
    ids = [int(i) for i in ids if i.isdigit()]
    from apps.export_app.services import build_export_response
    products = Product.objects.filter(id__in=ids).select_related('country')
    countries = set(p.country.code for p in products)
    fn = f'tkerp_export_{countries.pop()}' if len(countries) == 1 else 'tkerp_export_all'
    return build_export_response(ids, filename=fn)

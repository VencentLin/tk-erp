"""运营面板视图"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import HttpResponse
from django.db.models import Count

from apps.patterns.models import Pattern
from apps.templates_app.models import TShirtTemplate
from apps.products.models import Product
from apps.core.models import Country
from apps.patterns.batch_import import batch_import_patterns

staff_required = user_passes_test(lambda u: u.is_staff, login_url='/admin/login/')


@staff_required
def index(request):
    """Dashboard 首页"""
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


@staff_required
def pattern_list(request):
    """印花列表"""
    patterns = Pattern.objects.filter(is_deleted=False).order_by('-created_at')
    ctx = {
        'patterns': patterns,
        'source_types': Pattern.SOURCE_CHOICES,
    }
    return render(request, 'dashboard/pattern_list.html', ctx)


@staff_required
def pattern_upload(request):
    """上传印花（支持多文件）"""
    if request.method == 'POST':
        files = request.FILES.getlist('images')
        source_type = request.POST.get('source_type', 'clean_print')
        note = request.POST.get('note', '')

        for f in files:
            if f.size > 0:
                Pattern.objects.create(
                    image=f,
                    uploaded_by=request.user,
                    source_type=source_type,
                    note=note or f.name,
                )

        messages.success(request, f'成功上传 {len(files)} 张印花')
        return redirect('pattern_list')

    return render(request, 'dashboard/pattern_upload.html')


@staff_required
def pattern_batch(request):
    """批量导入"""
    ctx = {'results': None, 'error': None}

    if request.method == 'POST':
        try:
            uploaded_files = request.FILES.getlist('images')
            excel_file = request.FILES.get('excel_file')

            excel_data = None
            if excel_file and excel_file.size > 0:
                excel_data = excel_file.read()

            results = batch_import_patterns(
                files=uploaded_files if uploaded_files else None,
                excel_file=excel_data,
                uploaded_by=request.user,
            )

            ctx['results'] = results
            ctx['new_count'] = sum(1 for r in results if r.status == 'new')
            ctx['dup_count'] = sum(1 for r in results if r.status == 'duplicate')
            ctx['err_count'] = sum(1 for r in results if r.status == 'error')
            messages.success(request, f'导入完成: {ctx["new_count"]} 新增, {ctx["dup_count"]} 重复, {ctx["err_count"]} 失败')

        except Exception as e:
            import traceback
            ctx['error'] = f'{type(e).__name__}: {e}\n{traceback.format_exc()}'

    return render(request, 'dashboard/pattern_batch.html', ctx)


@staff_required
def template_list(request):
    """T恤模板列表"""
    templates = TShirtTemplate.objects.filter(is_active=True).order_by('-created_at')
    ctx = {'templates': templates}
    return render(request, 'dashboard/template_list.html', ctx)


@staff_required
def template_upload(request):
    """上传T恤模板"""
    if request.method == 'POST':
        name = request.POST.get('name', '')
        color = request.POST.get('color', 'white')
        image = request.FILES.get('image')

        if image:
            TShirtTemplate.objects.create(name=name, color=color, image=image)
            messages.success(request, '模板上传成功')
            return redirect('template_list')

    return render(request, 'dashboard/template_upload.html')


@staff_required
def product_list(request):
    """产品列表"""
    country_code = request.GET.get('country', '')
    status = request.GET.get('status', '')

    products = Product.objects.select_related('country', 'pattern', 'template').order_by('-created_at')

    if country_code:
        products = products.filter(country__code=country_code)
    if status:
        products = products.filter(status=status)

    ctx = {
        'products': products,
        'countries': Country.objects.all(),
        'statuses': Product.STATUS_CHOICES,
        'selected_country': country_code,
        'selected_status': status,
    }
    return render(request, 'dashboard/product_list.html', ctx)


@staff_required
def product_export(request):
    """导出产品"""
    ids = request.GET.getlist('ids')
    if not ids:
        messages.error(request, '请先选择要导出的产品')
        return redirect('product_list')

    ids = [int(i) for i in ids if i.isdigit()]
    from apps.export_app.services import build_export_response

    products = Product.objects.filter(id__in=ids).select_related('country')
    countries = set(p.country.code for p in products)
    if len(countries) == 1:
        return build_export_response(ids, filename=f'tkerp_export_{countries.pop()}')
    return build_export_response(ids, filename='tkerp_export_all')

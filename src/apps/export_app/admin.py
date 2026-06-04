from django.contrib import admin, messages
from django.http import HttpResponseRedirect, HttpResponse
from apps.products.models import Product
from .services import build_export_response, export_products_csv


def export_as_zip(modeladmin, request, queryset):
    ids = list(queryset.values_list('id', flat=True))
    if not ids:
        messages.error(request, '请先选择要导出的产品')
        return HttpResponseRedirect(request.get_full_path())
    products = Product.objects.filter(id__in=ids).select_related('country')
    countries = set(p.country.code for p in products)
    if len(countries) == 1:
        return build_export_response(ids, filename=f'tkerp_export_{countries.pop()}')
    return build_export_response(ids, filename='tkerp_export_all')

export_as_zip.short_description = '导出选中的产品（ZIP：CSV+图片）'


def export_as_csv(modeladmin, request, queryset):
    ids = list(queryset.values_list('id', flat=True))
    if not ids:
        messages.error(request, '请先选择要导出的产品')
        return HttpResponseRedirect(request.get_full_path())
    csv_content = export_products_csv(ids)
    response = HttpResponse(csv_content, content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="tkerp_export.csv"'
    return response

export_as_csv.short_description = '导出选中的产品（CSV）'

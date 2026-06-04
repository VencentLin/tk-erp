"""产品导出 — CSV + 图片包"""
import csv
import io
import zipfile
from django.http import HttpResponse
from apps.products.models import Product


def export_products_csv(product_ids: list[int]) -> str:
    products = Product.objects.filter(id__in=product_ids).select_related('country')
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Product ID', 'Title', 'Description', 'Size', 'Country',
                      'Print Image URL', 'Mockup URL', 'Status', 'Created At'])
    for p in products:
        writer.writerow([p.id, p.title, p.description, p.size_info, p.country.name,
                         p.print_image.url if p.print_image else '',
                         p.mockup_image.url if p.mockup_image else '',
                         p.get_status_display(), p.created_at.strftime('%Y-%m-%d %H:%M')])
    return output.getvalue()


def export_products_zip(product_ids: list[int]) -> bytes:
    products = Product.objects.filter(id__in=product_ids).select_related('country')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('products.csv', export_products_csv(product_ids))
        for p in products:
            if p.print_image:
                try:
                    zf.writestr(f'images/{p.id}_print.png', p.print_image.read())
                except Exception:
                    pass
            if p.mockup_image:
                try:
                    zf.writestr(f'images/{p.id}_mockup.png', p.mockup_image.read())
                except Exception:
                    pass
    buf.seek(0)
    return buf.getvalue()


def build_export_response(product_ids: list[int], filename: str = 'export') -> HttpResponse:
    zip_data = export_products_zip(product_ids)
    response = HttpResponse(zip_data, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{filename}.zip"'
    return response

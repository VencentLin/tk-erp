"""产品导出 — CSV + 图片包 (V2)"""
import csv, io, zipfile
from django.http import HttpResponse
from apps.products.models import Product


def export_products_csv(product_ids):
    products = Product.objects.filter(id__in=product_ids).prefetch_related('skus__template').select_related('country', 'category', 'prompt_preset')
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Product ID', 'Title', 'Description', 'Size', 'Country', 'Category', 'SKU Colors', 'Status', 'Created At'])
    for p in products:
        sku_colors = ', '.join(
            (s.template.get_color_display() if s.template else f'SKU#{s.id}')
            for s in p.skus.all()
        )
        # V7: category fallback — prompt_preset > category > '-'
        if p.prompt_preset:
            category_name = p.prompt_preset.name
        elif p.category:
            category_name = p.category.name
        else:
            category_name = '-'
        writer.writerow([p.id, p.title, p.description, p.size_info, p.country.name, category_name, sku_colors, p.get_status_display(), p.created_at.strftime('%Y-%m-%d %H:%M')])
    return output.getvalue()


def export_products_zip(product_ids):
    products = Product.objects.filter(id__in=product_ids).prefetch_related('skus').select_related('country', 'category', 'prompt_preset')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('products.csv', export_products_csv(product_ids))
        for p in products:
            for sku in p.skus.all():
                if sku.mockup_image:
                    try: zf.writestr(f'images/{p.id}_sku{sku.id}.jpg', sku.mockup_image.read())
                    except Exception: pass
    buf.seek(0)
    return buf.getvalue()


def build_export_response(product_ids, filename='export'):
    return HttpResponse(export_products_zip(product_ids), content_type='application/zip',
                        headers={'Content-Disposition': f'attachment; filename="{filename}.zip"'})

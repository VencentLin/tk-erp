"""AI 生成完整流水线编排"""
import logging
from celery import chain, group, shared_task
from .preprocessing import remove_background_task
from .image_gen import generate_print_variants_task
from .text_gen import generate_product_text_task

logger = logging.getLogger(__name__)


@shared_task
def run_generation_pipeline(pattern_id: int, product_ids: list[int],
                            skip_preprocess: bool = False, variant_count: int = 4) -> dict:
    from apps.patterns.models import Pattern
    from apps.products.models import Product

    try:
        pattern = Pattern.objects.get(id=pattern_id)
    except Pattern.DoesNotExist:
        return {'success': False, 'pattern_id': pattern_id, 'error': 'Pattern not found'}

    Product.objects.filter(id__in=product_ids).update(status='processing')

    tasks = []

    if not skip_preprocess and pattern.source_type != 'clean_print':
        tasks.append(remove_background_task.si(pattern_id))

    image_tasks = [
        generate_print_variants_task.si(pattern_id=pattern_id, product_id=pid, variant_count=variant_count)
        for pid in product_ids
    ]
    if image_tasks:
        tasks.append(group(image_tasks))

    text_tasks = [generate_product_text_task.si(product_id=pid) for pid in product_ids]
    if text_tasks:
        tasks.append(group(text_tasks))

    if tasks:
        workflow = chain(*tasks)
        workflow.apply_async()

    return {'success': True, 'pattern_id': pattern_id, 'products_processed': len(product_ids), 'error': None}


@shared_task
def batch_upload_pipeline(pattern_ids: list[int], country_code: str,
                          template_id: int, variant_count: int = 4) -> dict:
    from apps.core.models import Country
    from apps.products.models import Product
    from apps.patterns.models import Pattern
    from apps.templates_app.models import TShirtTemplate

    try:
        country = Country.objects.get(code=country_code)
        template = TShirtTemplate.objects.get(id=template_id)
    except (Country.DoesNotExist, TShirtTemplate.DoesNotExist):
        return {'success': False, 'products_created': 0, 'error': 'Country or Template not found'}

    products_created = 0
    for pid in pattern_ids:
        try:
            pattern = Pattern.objects.get(id=pid)
        except Pattern.DoesNotExist:
            continue

        product = Product.objects.create(country=country, pattern=pattern, template=template, status='pending')
        run_generation_pipeline.delay(
            pattern_id=pid, product_ids=[product.id],
            skip_preprocess=(pattern.source_type == 'clean_print'),
            variant_count=variant_count,
        )
        products_created += 1

    return {'success': products_created > 0, 'products_created': products_created,
            'error': None if products_created > 0 else 'No valid patterns found'}

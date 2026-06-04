"""商品文本生成 Celery 任务"""
import logging
import time
from celery import shared_task
from apps.generation.ollama import OllamaProvider
from ai.prompts.loader import build_text_prompt

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def generate_product_text_task(self, product_id: int) -> dict:
    from apps.products.models import Product, GenerationLog

    try:
        product = Product.objects.select_related('country').get(id=product_id)
    except Product.DoesNotExist:
        return {'success': False, 'product_id': product_id, 'error': 'Product not found'}

    try:
        language_map = {'ID': 'id', 'TH': 'th'}
        language = language_map.get(product.country.code, 'id')

        provider = OllamaProvider()

        analysis_desc = 'stylish print design'
        if product.print_image:
            try:
                from PIL import Image
                import io
                data = product.print_image.read()
                img = Image.open(io.BytesIO(data))
                analysis = provider.analyze_image(img)
                analysis_desc = analysis.description or analysis_desc
            except Exception as e:
                logger.warning(f'Image analysis failed for Product #{product_id}: {e}')

        prompt = build_text_prompt(language=language, print_description=analysis_desc,
                                   colors='', style='', shirt_color='white/black')

        t0 = time.time()
        result = provider.generate_text(prompt, language=language)
        duration = int((time.time() - t0) * 1000)

        product.title = result.title
        product.description = result.description
        product.size_info = result.size_info
        product.status = 'completed'
        product.save()

        GenerationLog.objects.create(
            product=product, step='text_gen', model_used=provider.model,
            params={'language': language}, duration_ms=duration,
        )

        logger.info(f'Text generated for Product #{product_id}: {result.title[:50]}')
        return {'success': True, 'product_id': product_id, 'title': result.title, 'error': None}

    except Exception as exc:
        logger.error(f'Text generation failed for Product #{product_id}: {exc}')
        try:
            self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            Product.objects.filter(id=product_id).update(status='text_pending', error_message=str(exc))
            return {'success': False, 'product_id': product_id, 'error': str(exc)}

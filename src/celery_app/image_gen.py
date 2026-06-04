"""印花图像生成 Celery 任务"""
import io
import logging
import time
from PIL import Image
from celery import shared_task
from django.core.files.base import ContentFile

from apps.generation.comfyui import ComfyUIProvider
from apps.generation.provider import AnalysisResult
from apps.generation.variants import get_variant_directions, apply_variant
from ai.prompts.loader import build_image_prompt

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def generate_print_variants_task(self, pattern_id: int, product_id: int,
                                 variant_count: int = 4,
                                 negative_prompt: str = '') -> dict:
    from apps.patterns.models import Pattern
    from apps.products.models import Product, GenerationLog

    try:
        pattern = Pattern.objects.get(id=pattern_id)
        product = Product.objects.get(id=product_id)
    except (Pattern.DoesNotExist, Product.DoesNotExist):
        return {'success': False, 'product_id': product_id, 'error': 'Pattern or Product not found'}

    try:
        pattern_data = pattern.image.read()
        reference = Image.open(io.BytesIO(pattern_data)).convert('RGB')

        analysis_tags = []
        provider = ComfyUIProvider()
        directions = get_variant_directions(max_variants=variant_count)

        generated_count = 0
        t0 = time.time()

        for direction in directions:
            analysis = AnalysisResult(tags=analysis_tags or ['print', 'design'], colors=[], description='')
            style_param, color_param = apply_variant(direction, analysis)
            pos_prompt, neg_prompt, params = build_image_prompt(
                direction['config_key'],
                original_style=style_param,
                colors_or_style=color_param,
            )
            neg_prompt = negative_prompt or neg_prompt

            try:
                result = provider.generate_image(
                    prompt=pos_prompt,
                    reference_image=reference if direction['key'] != 'composition_tweak' else None,
                    params=params,
                )
            except Exception as e:
                logger.error(f'ComfyUI generation failed for direction {direction["key"]}: {e}')
                continue

            for i, img in enumerate(result.images):
                buf = io.BytesIO()
                img.save(buf, format='PNG')
                buf.seek(0)
                product.print_image.save(
                    f'product_{product_id}_{direction["key"]}_{i}.png',
                    ContentFile(buf.getvalue()), save=True,
                )
                generated_count += 1
                break

            duration = int((time.time() - t0) * 1000)
            GenerationLog.objects.create(
                product=product, step='image_gen', model_used='sdxl',
                params={'variant': direction['key'], 'prompt': pos_prompt,
                        'cfg_scale': params.get('cfg_scale', 7.0), 'steps': params.get('steps', 30)},
                duration_ms=duration,
            )

        product.status = 'text_pending' if generated_count > 0 else 'failed'
        product.save(update_fields=['status'])

        return {'success': generated_count > 0, 'product_id': product_id,
                'variants_generated': generated_count,
                'error': None if generated_count > 0 else 'No variants were generated'}

    except Exception as exc:
        logger.error(f'Image generation failed for Product #{product_id}: {exc}')
        try:
            self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            Product.objects.filter(id=product_id).update(status='failed', error_message=str(exc))
            return {'success': False, 'product_id': product_id, 'error': str(exc)}

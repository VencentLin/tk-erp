"""印花预处理任务：抠图 + 去背景"""
import io
import logging
from PIL import Image
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def remove_background_task(self, pattern_id: int) -> dict:
    from apps.patterns.models import Pattern

    try:
        pattern = Pattern.objects.get(id=pattern_id)
    except Pattern.DoesNotExist:
        return {'success': False, 'pattern_id': pattern_id, 'error': 'Pattern not found'}

    if not pattern.image:
        return {'success': False, 'pattern_id': pattern_id, 'error': 'No image file'}

    try:
        from rembg import remove

        input_data = pattern.image.read()
        input_image = Image.open(io.BytesIO(input_data)).convert('RGBA')
        output_image = remove(input_image)

        output_buffer = io.BytesIO()
        output_image.save(output_buffer, format='PNG')
        output_buffer.seek(0)

        from django.core.files.base import ContentFile
        filename = f'pattern_{pattern_id}_nobg.png'
        pattern.image.save(filename, ContentFile(output_buffer.getvalue()), save=True)
        pattern.source_type = 'clean_print'
        pattern.save(update_fields=['source_type'])

        logger.info(f'Pattern #{pattern_id} background removed successfully')
        return {'success': True, 'pattern_id': pattern_id, 'error': None}

    except Exception as exc:
        logger.error(f'Failed to remove background for Pattern #{pattern_id}: {exc}')
        try:
            self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {'success': False, 'pattern_id': pattern_id, 'error': str(exc)}

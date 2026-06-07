"""Management command: 补全 text_pending 产品的标题和描述（只补文案，不生成图片）"""
from django.core.management.base import BaseCommand
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent


class Command(BaseCommand):
    help = 'Backfill text for text_pending products (pod/source_image)'

    def handle(self, *args, **options):
        from apps.products.models import Product
        from apps.dashboard.views import _generate_text_v2

        qs = Product.objects.filter(status='text_pending', title='', generation_mode__in=['pod', 'source_image'])
        total = qs.count()
        if total == 0:
            self.stdout.write('No text_pending products found.')
            return

        success, failed = 0, 0
        for p in qs:
            try:
                if str(PROJECT_ROOT) not in sys.path:
                    sys.path.insert(0, str(PROJECT_ROOT))
                _generate_text_v2(p.id)
                p.refresh_from_db()
                p.status = 'completed'
                p.error_message = ''
                p.save(update_fields=['status', 'error_message'])
                success += 1
                self.stdout.write(f'Fixed #{p.id}: {p.title[:60]}')
            except Exception as e:
                failed += 1
                p.error_message = str(e)[:500]
                p.save(update_fields=['error_message'])
                self.stdout.write(self.style.ERROR(f'Failed #{p.id}: {e}'))

        self.stdout.write(self.style.SUCCESS(
            f'Text backfill completed: success={success} failed={failed}'
        ))

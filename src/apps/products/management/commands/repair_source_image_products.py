"""Management command: 修复卡在 processing 的 source_image 产品"""
import sys, os, threading
from pathlib import Path
from django.core.management.base import BaseCommand

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent


class Command(BaseCommand):
    help = 'Repair stuck source_image products (processing → run text gen)'

    def handle(self, *args, **options):
        from apps.products.models import Product
        from apps.dashboard.views import _run_source_image_text_generation

        products = Product.objects.filter(generation_mode='source_image', status='processing')
        count = products.count()
        if count == 0:
            self.stdout.write('No stuck source_image products found.')
            return

        self.stdout.write(f'Found {count} stuck source_image products. Generating text...')
        for p in products:
            self.stdout.write(f'  Repairing Product #{p.id}...')
            threading.Thread(target=_run_source_image_text_generation, args=(p.id,), daemon=True).start()

        self.stdout.write(self.style.SUCCESS(
            f'Started text generation for {count} products. Check product list for results.'
        ))

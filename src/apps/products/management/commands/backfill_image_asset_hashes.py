"""Management command: 补齐 ImageAsset 的 SHA256 file_hash"""
import hashlib
from django.core.management.base import BaseCommand
from apps.products.models import ImageAsset


class Command(BaseCommand):
    help = 'Backfill SHA256 file_hash for existing ImageAsset records'

    def handle(self, *args, **options):
        filled, skipped, errors = 0, 0, 0
        for asset in ImageAsset.objects.all():
            if asset.file_hash:
                skipped += 1
                continue
            try:
                data = asset.image.read()
                asset.file_hash = hashlib.sha256(data).hexdigest()
                asset.save(update_fields=['file_hash'])
                filled += 1
            except Exception as e:
                self.stderr.write(f'Error {asset.id}: {e}')
                errors += 1

        self.stdout.write(self.style.SUCCESS(
            f'Done: {filled} filled, {skipped} already hashed, {errors} errors'
        ))

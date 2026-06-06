"""Management command: 清理不在磁盘上或不在同步源中的旧 PromptPreset"""
from pathlib import Path
from django.core.management.base import BaseCommand
from apps.categories.models import PromptPreset

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent.parent


def _norm_rel_path(value: str) -> str:
    """统一路径分隔符为 /"""
    return str(value or '').replace('\\', '/')


class Command(BaseCommand):
    help = '删除/停用磁盘文件不存在的旧 PromptPreset'

    def handle(self, *args, **options):
        deleted, deactivated, skipped = 0, 0, 0
        for p in PromptPreset.objects.all():
            rel = _norm_rel_path(p.md_file or '').lower()

            # 不属于 data/prompts/ 目录 → 手动上传的，不处理
            if not rel.startswith('data/prompts/'):
                skipped += 1
                continue

            # 检查磁盘文件是否存在
            disk_path = None
            if p.md_file:
                disk_path = PROJECT_ROOT / str(p.md_file)
            file_exists = disk_path and disk_path.exists() if disk_path else False

            if file_exists:
                # 文件还在 → 保留
                skipped += 1
                continue

            # 文件不存在
            if p.products.count() == 0:
                # 无产品 → 硬删除
                p.delete()
                deleted += 1
                self.stdout.write(f'Deleted: {p.name} (file gone: {rel})')
            else:
                # 有产品 → 停用
                p.is_active = False
                p.save(update_fields=['is_active'])
                deactivated += 1
                self.stdout.write(f'Deactivated (has products): {p.name}')

        self.stdout.write(self.style.SUCCESS(
            f'Done: {deleted} deleted, {deactivated} deactivated, {skipped} skipped'
        ))

"""Management command: 从 data/print_prompts/ 目录同步 PrintDesignPreset 到数据库"""
from django.core.management.base import BaseCommand
from apps.categories.prompt_sync import sync_print_presets_from_disk


class Command(BaseCommand):
    help = '从 data/print_prompts/{white,black}/ 目录同步 .md 印花提示词到 PrintDesignPreset 表'

    def handle(self, *args, **options):
        self.stdout.write('Syncing print prompts from disk...')
        result = sync_print_presets_from_disk()
        self.stdout.write(self.style.SUCCESS(
            f'Done: {result["created"]} created, {result["updated"]} updated, '
            f'{result["deactivated"]} deactivated'
        ))
        if result['errors']:
            for err in result['errors']:
                self.stderr.write(self.style.ERROR(f'Error: {err}'))

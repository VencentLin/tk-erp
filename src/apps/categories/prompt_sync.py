"""V7: 从 data/prompts/ 目录自动同步 PromptPreset 到数据库"""
import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
PROMPTS_DIR = PROJECT_ROOT / 'data' / 'prompts'


def _parse_md_prompt(content: str) -> tuple:
    """解析 .md 文件 → (positive_prompt, negative_prompt) — 本地副本，避免跨模块依赖"""
    positive = content
    negative = ''

    neg_markers = ['## NEGATIVE', '## Negative', '## 负面 Prompt', '## 负面提示词']
    for marker in neg_markers:
        if marker in content:
            parts = content.split(marker, 1)
            positive = parts[0].strip()
            if len(parts) > 1:
                negative = parts[1].strip()
            break

    if not negative and '---' in content:
        parts = content.split('---', 1)
        positive = parts[0].strip()
        if len(parts) > 1:
            negative = parts[1].strip()

    positive = _strip_md_headers(positive)
    negative = _strip_md_headers(negative)
    return positive, negative


def _strip_md_headers(text: str) -> str:
    """去掉 ## 标题行，仅保留正文内容"""
    if not text:
        return ''
    lines = []
    for line in text.split('\n'):
        stripped = line.strip()
        if stripped.startswith('#'):
            continue
        if not stripped or stripped == '---':
            continue
        lines.append(stripped)
    return '\n'.join(lines).strip()


def _normalize_preset_prompt(text: str) -> str:
    """替换 .md 中遗留的占位符"""
    if not text:
        return text
    text = text.replace(
        '{{template_prompt}}',
        'white cotton t-shirt, crew neck, short sleeve, regular fit, '
        'realistic fabric texture, natural folds, large printable area'
    )
    text = text.replace('{{fabric}}', 'cotton fabric')
    text = text.replace('{{background}}',
        'wooden hanger, closet background, warm indoor lighting')
    return text


def _normalize_risky_keywords(text: str) -> tuple:
    """V7.1: 标准化高风险词为安全表达，返回 (normalized_text, warnings)"""
    warnings = []
    replacements = [
        # 后背印花 → 胸口
        ('back print', 'chest print', 'back print'),
        ('center back', 'center chest', 'center back'),
        ('upper back', 'upper chest', 'upper back'),
        ('full back', 'center chest', 'full back'),
        # 过大印花 → 小印花
        ('large graphic print', 'small to medium graphic print', 'large graphic print'),
        ('large graphic', 'small to medium graphic', 'large graphic'),
        ('oversized print', 'small chest print', 'oversized print'),
        ('all-over print', 'chest print', 'all-over print'),
        ('full shirt print', 'chest print', 'full shirt print'),
        # 立体/刺绣 → 平面
        ('embroidered patch', 'flat ink print', 'embroidered patch'),
        ('embroidery', 'flat ink print', 'embroidery'),
        ('stitched patch', 'flat ink print', 'stitched patch'),
        ('applique', 'flat ink print', 'applique'),
        ('3d print', 'flat ink print', '3d print'),
        ('raised print', 'flat ink print', 'raised print'),
        ('rubber patch', 'flat ink print', 'rubber patch'),
        ('puffy print', 'flat ink print', 'puffy print'),
        ('sewn-on badge', 'flat printed emblem', 'sewn-on badge'),
        # patch-like → flat graphic
        ('patch-like', 'flat graphic', 'patch-like'),
        # diagonal crossing stroke → 安全
        ('diagonal crossing stroke', 'curved abstract stroke', 'diagonal crossing stroke'),
        ('large diagonal band', 'small curved accent', 'large diagonal band'),
        # screen-print texture → 安全
        ('screen-print texture', 'flat ink texture', 'screen-print texture'),
        # badge → flat emblem (只在独立出现时)
        ('sewn badge', 'flat printed emblem', 'sewn badge'),
    ]
    result = text
    for old, new, keyword in replacements:
        if old in result.lower():
            result = result.replace(old, new)
            if keyword not in warnings:
                warnings.append(keyword)
    return result, warnings


def _detect_shirt_color(filename: str, dir_name: str = '') -> str:
    """从文件名/目录名识别 T 恤颜色"""
    combined = (dir_name + '/' + filename).lower()
    if 'black' in combined:
        return 'black'
    if 'white' in combined:
        return 'white'
    return 'other'


def sync_prompt_presets_from_disk(prompts_dir: Path = None) -> dict:
    """扫描 data/prompts/ 下 white/black 子目录，创建或更新 PromptPreset。

    Returns: {'created': N, 'updated': N, 'deactivated': N, 'errors': [...]}
    """
    from apps.categories.models import PromptPreset

    if prompts_dir is None:
        prompts_dir = PROMPTS_DIR

    result = {'created': 0, 'updated': 0, 'deactivated': 0, 'errors': []}

    # 收集有效的同步来源
    sync_sources = {}  # slug -> {path, shirt_color}

    # 扫描 white/ 和 black/ 子目录
    for color_dir_name in ('white', 'black'):
        color_path = prompts_dir / color_dir_name
        if not color_path.is_dir():
            continue
        for md_file in sorted(color_path.glob('*.md')):
            try:
                content = md_file.read_text(encoding='utf-8')
            except Exception as e:
                result['errors'].append(f'Read error {md_file}: {e}')
                continue

            # 用文件名 + 目录生成 slug
            rel_path = md_file.relative_to(prompts_dir)
            slug = str(rel_path.with_suffix('')).replace('\\', '/').replace('/', '-').replace(' ', '-').lower()

            shirt_color = _detect_shirt_color(md_file.name, color_dir_name)
            sync_sources[slug] = {
                'path': md_file,
                'content': content,
                'shirt_color': shirt_color,
                'name': md_file.stem.replace('-', ' ').replace('_', ' ').strip(),
            }

    # NOTE: 不扫描根目录 .md 文件 — 仅 white/ 和 black/ 子目录是同步源

    # 创建/更新数据库记录
    created_slugs = set()
    for slug, info in sync_sources.items():
        try:
            positive, negative = _parse_md_prompt(info['content'])
            positive = _normalize_preset_prompt(positive)
            positive, warnings = _normalize_risky_keywords(positive)
            if warnings:
                result['errors'].append(f'Risky keywords normalized in {slug}: {", ".join(warnings)}')

            existing = PromptPreset.objects.filter(slug=slug).first()
            if existing:
                existing.content = positive
                existing.negative_prompt = negative
                existing.shirt_color = info['shirt_color']
                existing.name = info['name']
                # 更新 md_file 指向
                try:
                    rel = info['path'].relative_to(PROJECT_ROOT)
                    existing.md_file = str(rel)
                except ValueError:
                    pass
                existing.is_active = True
                existing.save()
                result['updated'] += 1
            else:
                rel = str(info['path'].relative_to(PROJECT_ROOT))
                PromptPreset.objects.create(
                    name=info['name'], slug=slug,
                    content=positive, negative_prompt=negative,
                    shirt_color=info['shirt_color'],
                    md_file=rel,
                    is_active=True,
                )
                result['created'] += 1
            created_slugs.add(slug)
        except Exception as e:
            result['errors'].append(f'Sync error {slug}: {e}')

    # 清理不在同步源中的活跃预设
    stale = PromptPreset.objects.filter(is_active=True).exclude(slug__in=created_slugs)
    for preset in stale:
        rel = _norm_rel_path(preset.md_file or '').lower()
        # 只处理属于 data/prompts/ 目录的预设（保护手动上传的）
        if not rel.startswith('data/prompts/'):
            continue
        # 检查磁盘文件是否真实存在
        disk_path = PROJECT_ROOT / str(preset.md_file) if preset.md_file else None
        file_exists = disk_path and disk_path.exists() if disk_path else False

        if not file_exists:
            if preset.products.count() == 0:
                # 磁盘文件已删除 + 无产品关联 → 硬删除
                preset.delete()
                result['deactivated'] += 1  # 复用 deactivated 计数
            else:
                # 磁盘文件已删除 + 有产品关联 → 停用
                preset.is_active = False
                preset.save(update_fields=['is_active'])
                result['deactivated'] += 1
        # else: 磁盘文件还在但 slug 不匹配（可能被重命名），保留旧纪录

    return result


PRINT_PROMPTS_DIR = PROJECT_ROOT / 'data' / 'print_prompts'


def sync_print_presets_from_disk(prompts_dir: Path = None) -> dict:
    """扫描 data/print_prompts/ 下 white/black 子目录，创建或更新 PrintDesignPreset。

    Returns: {'created': N, 'updated': N, 'deactivated': N, 'errors': [...]}
    """
    from apps.categories.models import PrintDesignPreset

    if prompts_dir is None:
        prompts_dir = PRINT_PROMPTS_DIR

    result = {'created': 0, 'updated': 0, 'deactivated': 0, 'errors': []}
    sync_sources = {}

    for color_dir_name in ('white', 'black'):
        color_path = prompts_dir / color_dir_name
        if not color_path.is_dir():
            continue
        for md_file in sorted(color_path.glob('*.md')):
            try:
                content = md_file.read_text(encoding='utf-8')
            except Exception as e:
                result['errors'].append(f'Read error {md_file}: {e}')
                continue

            rel_path = md_file.relative_to(prompts_dir)
            slug = str(rel_path.with_suffix('')).replace('\\', '/').replace('/', '-').replace(' ', '-').lower()

            shirt_color = _detect_shirt_color(md_file.name, color_dir_name)
            sync_sources[slug] = {
                'path': md_file,
                'content': content,
                'shirt_color': shirt_color,
                'name': md_file.stem.replace('-', ' ').replace('_', ' ').strip(),
            }

    # 解析 variation_pool 从 .md
    created_slugs = set()
    for slug, info in sync_sources.items():
        try:
            positive, negative = _parse_md_prompt(info['content'])
            positive, warnings = _normalize_risky_keywords(positive)
            if warnings:
                result['errors'].append(f'Risky keywords normalized in {slug}: {", ".join(warnings)}')

            # 提取 VARIATION POOL
            import re
            pool_match = re.search(r'##\s*VARIATION\s*POOL\s*\n(.*?)(?=\n##|\Z)', info['content'], re.DOTALL | re.IGNORECASE)
            variation_pool = {}
            if pool_match:
                section = pool_match.group(1)
                current_key = None
                for line in section.strip().split('\n'):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if line.endswith(':') and not line.startswith('-'):
                        current_key = line[:-1].strip()
                        variation_pool[current_key] = []
                    elif line.startswith('- ') and current_key:
                        variation_pool[current_key].append(line[2:].strip())
                    elif line.startswith('-') and current_key:
                        variation_pool[current_key].append(line[1:].strip())

            existing = PrintDesignPreset.objects.filter(slug=slug).first()
            if existing:
                existing.content = positive
                existing.negative_prompt = negative
                existing.shirt_color = info['shirt_color']
                existing.name = info['name']
                existing.variation_pool = variation_pool
                try:
                    rel = info['path'].relative_to(PROJECT_ROOT)
                    existing.md_file = str(rel)
                except ValueError:
                    pass
                existing.is_active = True
                existing.save()
                result['updated'] += 1
            else:
                rel = str(info['path'].relative_to(PROJECT_ROOT))
                PrintDesignPreset.objects.create(
                    name=info['name'], slug=slug,
                    content=positive, negative_prompt=negative,
                    shirt_color=info['shirt_color'],
                    variation_pool=variation_pool,
                    md_file=rel,
                    is_active=True,
                )
                result['created'] += 1
            created_slugs.add(slug)
        except Exception as e:
            result['errors'].append(f'Sync error {slug}: {e}')

    # Cleanup stale presets
    stale = PrintDesignPreset.objects.filter(is_active=True).exclude(slug__in=created_slugs)
    for preset in stale:
        rel = _norm_rel_path(preset.md_file or '').lower()
        if not rel.startswith('data/print_prompts/'):
            continue
        disk_path = PROJECT_ROOT / str(preset.md_file) if preset.md_file else None
        file_exists = disk_path and disk_path.exists() if disk_path else False
        if not file_exists:
            if preset.designs.count() == 0:
                preset.delete()
                result['deactivated'] += 1
            else:
                preset.is_active = False
                preset.save(update_fields=['is_active'])
                result['deactivated'] += 1

    return result


def _norm_rel_path(value: str) -> str:
    """统一路径分隔符为 /"""
    return str(value or '').replace('\\', '/')

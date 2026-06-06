"""POD 印花随机变体生成器"""
import random
import re
from typing import Tuple


DEFAULT_VARIATION_POOL = {
    'color_palettes': [
        'coral red, sunny yellow, grass green, royal blue',
        'muted orange, cream, forest green, warm brown',
        'cobalt blue, white, soft purple, mint green',
        'pastel pink, lavender, baby blue, lemon yellow',
        'gold, deep navy, burgundy, cream',
        'neon green, black, hot pink, electric blue',
    ],
    'composition': [
        'compact center emblem',
        'circular decorative motif',
        'scattered icon cluster in a loose row',
        'single centered graphic symbol',
        'small chest-left logo placement',
    ],
    'elements': [
        'star, leaf, flower, abstract dot, circle',
        'flame, wave, geometric block, stripe',
        'heart, sun, moon, cloud, bird silhouette',
        'diamond, triangle, hexagon, concentric rings',
        'feather, droplet, spiral, crosshatch',
    ],
    'texture': [
        'flat ink print, clean vector look',
        'slightly distressed flat ink, vintage feel',
        'clean vector ink, sharp edges',
        'soft ink bleed, hand-printed character',
    ],
}


def _parse_variation_pool_md(content: str) -> dict:
    """解析 .md 文件中的 ## VARIATION POOL 段（YAML-like 格式）"""
    pool = {}
    match = re.search(r'##\s*VARIATION\s*POOL\s*\n(.*?)(?=\n##|\Z)', content, re.DOTALL | re.IGNORECASE)
    if not match:
        return pool

    section = match.group(1)
    current_key = None
    for line in section.strip().split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        # key:
        if line.endswith(':') and not line.startswith('-'):
            current_key = line[:-1].strip()
            pool[current_key] = []
        # - value
        elif line.startswith('- ') and current_key:
            pool[current_key].append(line[2:].strip())
        # - value (no space)
        elif line.startswith('-') and current_key:
            pool[current_key].append(line[1:].strip())
    return pool


def build_random_print_prompt(preset, seed: int = None) -> Tuple[str, str, dict]:
    """根据 PrintDesignPreset 生成随机印花 prompt。

    Args:
        preset: PrintDesignPreset instance (has .content, .negative_prompt, .variation_pool)
        seed: 随机种子（可选，用于可重现）

    Returns:
        (positive_prompt, negative_prompt, metadata)
    """
    rng = random.Random(seed) if seed is not None else random.Random()

    # 解析 .md 内容中的 VARIATION POOL
    md_pool = _parse_variation_pool_md(preset.content)

    # 合并: .md pool 优先, 系统默认兜底
    pool = dict(DEFAULT_VARIATION_POOL)
    for key in ('color_palettes', 'composition', 'elements', 'texture'):
        if key in md_pool and md_pool[key]:
            pool[key] = md_pool[key]

    # 随机抽取
    chosen_palette = rng.choice(pool['color_palettes'])
    chosen_composition = rng.choice(pool['composition'])
    chosen_elements = rng.choice(pool['elements'])
    chosen_texture = rng.choice(pool['texture'])

    # 构建 positive prompt
    # 取 preset.content 中的主描述（去除 VARIATION POOL 和 NEGATIVE 段）
    base_description = preset.content
    # 去掉 VARIATION POOL 段
    base_description = re.sub(r'##\s*VARIATION\s*POOL\s*\n.*?(?=\n##|\Z)', '', base_description, flags=re.DOTALL | re.IGNORECASE)
    # 去掉 NEGATIVE 段
    base_description = re.sub(r'##\s*NEGATIVE\s*\n.*$', '', base_description, flags=re.DOTALL | re.IGNORECASE)
    base_description = base_description.strip()

    positive = (
        f'{base_description}\n'
        f'color palette: {chosen_palette}\n'
        f'composition: {chosen_composition}\n'
        f'elements: {chosen_elements}\n'
        f'texture: {chosen_texture}\n'
        'flat graphic design, no text, no letters, no logo, no human, white background'
    )

    negative = preset.negative_prompt or (
        'text, letters, words, typography, human, face, body, hand, '
        'logo, watermark, mockup, t-shirt, clothing, hanger, product photo, '
        '3d, embroidery, patch, pocket, photo, realistic photo'
    )

    metadata = {
        'palette': chosen_palette,
        'composition': chosen_composition,
        'elements': chosen_elements,
        'texture': chosen_texture,
        'seed': seed,
        'pool_source': 'md' if md_pool else 'default',
    }

    return positive, negative, metadata

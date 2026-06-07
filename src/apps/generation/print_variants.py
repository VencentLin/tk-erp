"""POD 印花随机变体生成器 — 只生成独立平面图案，不生成 T 恤/商品图"""
import random
import re
from typing import Tuple

# POD 核心产品定义：独立的流行视觉符号 / logo-like 图案 / 表情包 / 装饰图案
POD_PRINT_SYSTEM_PROMPT = (
    'Create one standalone print-ready graphic artwork. '
    'The design can be a trending emblem, abstract logo mark, meme-inspired icon, '
    'streetwear symbol, tattoo-flash graphic, ornamental motif, or bold decorative mark. '
    'Use varied silhouettes and style families. '
    'Avoid making every design cute, kawaii, childish, or mascot-like. '
    'Frames and borders are optional, not default. '
    'No readable text, no letters, no brand names. '
    'No clothing, no t-shirt, no apparel mockup, no product photo, no scene. '
    'Do not show the artwork printed on anything. '
    'Flat print-ready graphic with clean edges, suitable for screen print or DTG. '
    'Centered isolated artwork, removable background.'
)

_STYLE_FAMILIES = {
    'street': {'weight': 3, 'loras': (0.65, 0.8)},
    'abstract': {'weight': 3, 'loras': (0.5, 0.7)},
    'vintage': {'weight': 3, 'loras': (0.6, 0.8)},
    'grunge': {'weight': 2, 'loras': (0.55, 0.75)},
    'cyber': {'weight': 2, 'loras': (0.65, 0.85)},
    'botanical': {'weight': 2, 'loras': (0.5, 0.7)},
    'gothic': {'weight': 2, 'loras': (0.6, 0.8)},
    'surreal': {'weight': 2, 'loras': (0.55, 0.75)},
    'comic': {'weight': 2, 'loras': (0.6, 0.8)},
    'minimal': {'weight': 2, 'loras': (0.45, 0.65)},
    'meme': {'weight': 2, 'loras': (0.7, 0.9)},
    'cute': {'weight': 1, 'loras': (0.7, 0.9)},
}

DEFAULT_VARIATION_POOL = {
    'theme': [
        'streetwear bold emblem',
        'abstract geometric logo mark',
        'vintage tattoo flash graphic',
        'grunge skate sticker graphic',
        'cyberpunk chrome symbol',
        'minimal modern icon mark',
        'retro surf badge without text',
        'botanical ornamental graphic',
        'dark gothic ornamental symbol',
        'pop surreal object icon',
        'halftone comic graphic, not childish',
        'Y2K cyber icon',
        'meme-inspired sticker graphic',
        'kawaii mascot icon',
    ],
    'color_palettes': [
        'coral red, sunny yellow, grass green, royal blue',
        'muted orange, cream, forest green, warm brown',
        'cobalt blue, white, soft purple, mint green',
        'pastel pink, lavender, baby blue, lemon yellow',
        'gold, deep navy, burgundy, cream',
        'neon green, black, hot pink, electric blue',
        'chrome silver, cyber blue, dark purple, neon pink',
        'earth brown, olive green, rust orange, cream white',
        'blood red, charcoal black, bone white, muted gold',
    ],
    'composition': [
        'irregular die-cut sticker silhouette',
        'asymmetric floating accent cluster',
        'jagged freeform burst',
        'single centered icon',
        'drippy liquid contour',
        'organic freeform shape',
        'diagonal flying shape with no frame',
        'fragmented glitch silhouette',
        'bold centered emblem with sharp edges',
        'compact circular sticker',
    ],
    'elements': [
        'abstract lightning serpent, sharp sparks, broken rings',
        'chrome liquid heart, asymmetric droplets, star cuts',
        'vintage skull flower, ornamental leaves, sun rays',
        'geometric panther head, angular shards, bold outline',
        'retro mushroom planet, orbit rings, small stars',
        'flame eye symbol, checker fragments, spray dots',
        'botanical snake curve, thorn branches, crescent moon',
        'surf wave skull, sunburst, rough ink texture',
        'glitch butterfly, pixel shards, neon accents',
        'minimal lucky charm icon, freeform contour',
        'smiling blob mascot, star sparks, rounded shapes',
        'cartoon ghost, tiny hearts, sparkle marks',
    ],
    'style': [
        'bold screen-print streetwear graphic',
        'clean abstract logo mark',
        'vintage tattoo flash style',
        'distressed grunge sticker',
        'chrome cyberpunk symbol',
        'modern minimal icon',
        'retro pop art emblem',
        'Y2K internet culture icon',
        'botanical ornamental ink',
        'dark gothic decorative symbol',
        'pop surreal flat graphic',
        'halftone comic panel style',
        'flat vector sticker style',
        'Japanese kawaii graphic',
    ],
}

# T恤/衣服相关正向词 → 替换为印花图案语义
_TSHIRT_WORD_REPLACEMENTS = [
    ('t-shirt print design', 'printable graphic artwork'),
    ('t-shirt', 'standalone graphic'),
    ('shirt', 'flat artwork'),
    ('clothing', 'print-ready design'),
    ('garment', 'artwork'),
    ('apparel', 'print design'),
    ('for a black t-shirt', 'high contrast artwork suitable for dark backgrounds'),
    ('for a white t-shirt', 'artwork suitable for light backgrounds'),
    ('for black t-shirt', 'high contrast artwork suitable for dark backgrounds'),
    ('for white t-shirt', 'artwork suitable for light backgrounds'),
    ('chest print', 'compact centered print artwork'),
    ('graphic tee', 'streetwear graphic art'),
    ('printed on', 'designed as'),
    ('mockup', 'artwork'),
    ('product photo', 'print-ready graphic'),
    ('hanger', ''),
    ('fabric folds', ''),
    ('cotton', ''),
    ('sleeve', ''),
    ('collar', ''),
    ('wardrobe', ''),
    ('printed on black', 'suitable for dark backgrounds'),
    ('printed on white', 'suitable for light backgrounds'),
    ('black cotton', 'dark surface'),
    ('white cotton', 'light surface'),
]


def _sanitize_tshirt_words(text: str) -> str:
    """清除印花 prompt 中不应出现的 T 恤/衣服相关词"""
    result = text
    for old, new in _TSHIRT_WORD_REPLACEMENTS:
        if old in result.lower():
            result = re.sub(old, new, result, flags=re.IGNORECASE)
    # Remove double spaces caused by empty replacements
    result = re.sub(r'  +', ' ', result)
    result = re.sub(r',\s*,', ',', result)
    return result.strip()


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
        if line.endswith(':') and not line.startswith('-'):
            current_key = line[:-1].strip()
            pool[current_key] = []
        elif line.startswith('- ') and current_key:
            pool[current_key].append(line[2:].strip())
        elif line.startswith('-') and current_key:
            pool[current_key].append(line[1:].strip())
    return pool


def build_random_print_prompt(preset, seed: int = None) -> Tuple[str, str, dict]:
    """根据 PrintDesignPreset 生成随机印花 prompt。

    Returns:
        (positive_prompt, negative_prompt, metadata)
    """
    rng = random.Random(seed) if seed is not None else random.Random()

    # 解析 .md VARIATION POOL
    md_pool = _parse_variation_pool_md(preset.content)

    # Merge: .md pool 优先, 系统默认兜底
    pool = dict(DEFAULT_VARIATION_POOL)
    for key in ('theme', 'color_palettes', 'composition', 'elements', 'style'):
        if key in md_pool and md_pool[key]:
            pool[key] = md_pool[key]

    # 随机抽取
    chosen_theme = rng.choice(pool.get('theme', ['trendy sticker graphic']))
    chosen_palette = rng.choice(pool.get('color_palettes', pool['color_palettes']))
    chosen_composition = rng.choice(pool.get('composition', pool['composition']))
    chosen_elements = rng.choice(pool.get('elements', pool['elements']))
    chosen_style = rng.choice(pool.get('style', ['flat vector sticker style']))

    # 取 preset.content 主描述，清理 T 恤词
    base_description = preset.content
    base_description = re.sub(r'##\s*VARIATION\s*POOL\s*\n.*?(?=\n##|\Z)', '', base_description, flags=re.DOTALL | re.IGNORECASE)
    base_description = re.sub(r'##\s*NEGATIVE\s*\n.*$', '', base_description, flags=re.DOTALL | re.IGNORECASE)
    base_description = base_description.strip()
    base_description = _sanitize_tshirt_words(base_description)

    # Build positive prompt
    positive = (
        f'{POD_PRINT_SYSTEM_PROMPT}\n\n'
        f'{base_description}\n'
        f'theme: {chosen_theme}\n'
        f'color palette: {chosen_palette}\n'
        f'composition: {chosen_composition}\n'
        f'elements: {chosen_elements}\n'
        f'style: {chosen_style}'
    )

    # Negative prompt — 强制禁止 T 恤/衣服/商品图
    negative = preset.negative_prompt or ''
    # 确保 negative 包含关键禁止词
    required_negatives = [
        't-shirt', 'shirt', 'clothing', 'garment', 'apparel', 'mockup',
        'product photo', 'hanger', 'collar', 'sleeve', 'fabric folds',
        'rectangular background', 'white rectangle', 'poster', 'frame',
        'printed on shirt', 'model', 'wardrobe',
        'perfect oval frame', 'repeated oval badge', 'circular seal', 'rectangular card',
        'text', 'letters', 'words', 'typography', 'watermark',
        'brand logo', 'readable logo text', 'company logo', 'brand name',
        'human', 'face', 'body', 'hand',
        '3d', 'embroidery', 'patch', 'pocket',
    ]
    for kw in required_negatives:
        if kw not in negative.lower():
            negative += f', {kw}'
    negative = negative.strip(', ')

    metadata = {
        'theme': chosen_theme,
        'palette': chosen_palette,
        'composition': chosen_composition,
        'elements': chosen_elements,
        'style': chosen_style,
        'seed': seed,
        'pool_source': 'md' if md_pool else 'default',
    }

    return positive, negative, metadata

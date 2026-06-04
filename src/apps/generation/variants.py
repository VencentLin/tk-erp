"""印花变体策略"""
import random

VARIANT_DIRECTIONS = [
    {'key': 'color_shift', 'label': '换色系', 'config_key': 'color_shift'},
    {'key': 'style_transfer', 'label': '风格迁移', 'config_key': 'style_transfer'},
    {'key': 'element_add', 'label': '元素加减', 'config_key': 'element_add'},
    {'key': 'composition_tweak', 'label': '构图微调', 'config_key': 'composition_tweak'},
]

ALTERNATE_COLORS = [
    'warm sunset orange and pink', 'cool ocean blue and teal',
    'earthy brown and olive green', 'pastel pink and lavender',
    'bold red and navy', 'monochrome black and gray',
    'bright yellow and coral', 'forest green and cream',
]

ALTERNATE_STYLES = [
    'watercolor painting style', 'minimalist line art',
    'vintage retro 90s', 'Japanese ukiyo-e style',
    'streetwear graffiti style', 'bohemian ethnic pattern',
    'Scandinavian modern simple', 'pop art bold comic style',
]

ELEMENT_ADDITIONS = [
    'tropical leaves', 'small flowers', 'geometric shapes',
    'stars and sparkles', 'butterflies', 'abstract waves',
    'palm trees', 'celestial moon and sun',
]


def get_variant_directions(max_variants: int = 4) -> list[dict]:
    if max_variants >= len(VARIANT_DIRECTIONS):
        return VARIANT_DIRECTIONS
    return random.sample(VARIANT_DIRECTIONS, max_variants)


def apply_variant(direction: dict, analysis) -> tuple[str, str]:
    key = direction['key']

    if key == 'color_shift':
        new_colors = random.choice(ALTERNATE_COLORS)
        return ', '.join(analysis.tags), new_colors

    elif key == 'style_transfer':
        new_style = random.choice(ALTERNATE_STYLES)
        return new_style, ', '.join(analysis.colors) if analysis.colors else 'original'

    elif key == 'element_add':
        addition = random.choice(ELEMENT_ADDITIONS)
        combined = ', '.join(analysis.tags) if analysis.tags else ''
        return f'{combined} with {addition}', ', '.join(analysis.colors) if analysis.colors else 'vibrant'

    elif key == 'composition_tweak':
        return ', '.join(analysis.tags) if analysis.tags else '', ', '.join(analysis.colors) if analysis.colors else 'original'

    return '', ''

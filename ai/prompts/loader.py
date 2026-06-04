"""Prompt 模板加载工具"""
from pathlib import Path
import tomllib

PROMPTS_DIR = Path(__file__).resolve().parent


def load_image_variants_config() -> dict:
    """加载印花变体配置"""
    config_path = PROMPTS_DIR / 'image_variants.toml'
    with open(config_path, 'rb') as f:
        return tomllib.load(f)


def load_text_prompt(language: str, template_name: str) -> str:
    """加载文本生成 Prompt 模板

    Args:
        language: 'th' (泰文) or 'id' (印尼文)
        template_name: 'title' or 'description'
    """
    filename = f'{template_name}_{language}.txt'
    path = PROMPTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f'Prompt template not found: {path}')
    return path.read_text(encoding='utf-8')


def build_image_prompt(
    variant_type: str,
    original_style: str,
    colors_or_style: str,
) -> tuple[str, str, dict]:
    """构建图像生成的 prompt

    Returns:
        (positive_prompt, negative_prompt, extra_params)
    """
    config = load_image_variants_config()
    base = config['base_prompt']['template']
    neg = config['negative_prompt']['template']
    variant_cfg = config['variants'].get(variant_type, config['variants']['style_transfer'])

    # Build a format dict mapping all possible variant placeholder keys.
    # `original_style` covers the original pattern description;
    # `colors_or_style` covers new style / palette / element additions.
    format_kwargs = {
        'original_style': original_style,
        'original_colors': original_style,
        'new_style': colors_or_style,
        'new_color_palette': colors_or_style,
        'new_elements': colors_or_style,
    }

    # First pass: resolve placeholders inside the variant config values
    resolved_style_tags = variant_cfg.get('style_tags', original_style).format(**format_kwargs)
    color_scheme_raw = variant_cfg.get('color_scheme', colors_or_style)
    resolved_color_scheme = color_scheme_raw.format(**format_kwargs)

    # Second pass: format the base template with the resolved values
    prompt = base.format(
        style_tags=resolved_style_tags,
        color_scheme=resolved_color_scheme,
    )

    extra_params = {
        'denoising_strength': variant_cfg.get('denoising_strength', 0.65)
    }

    return prompt, neg, extra_params


def build_text_prompt(
    language: str,
    print_description: str,
    colors: str = '',
    style: str = '',
    shirt_color: str = ' putih / hitam',
) -> str:
    """构建商品文本生成的 prompt

    Args:
        language: 'th' or 'id'
        print_description: 印花特征描述
        colors: 主色调
        style: 风格标签
        shirt_color: T恤颜色
    """
    template = load_text_prompt(language, 'title')
    return template.format(
        print_description=print_description,
        colors=colors,
        style=style,
        shirt_color=shirt_color,
    )

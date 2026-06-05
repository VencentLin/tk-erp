from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent


def load_text_prompt(language: str, template_name: str) -> str:
    filename = f'{template_name}_{language}.txt'
    path = PROMPTS_DIR / filename
    if not path.exists():
        return ("You are a TikTok Shop product title expert. Write a concise, attractive product title "
                f"{'in Thai' if language == 'th' else 'in Indonesian'} based on: {{print_description}}. "
                "Keep it under 120 characters.")
    return path.read_text(encoding='utf-8')


def build_text_prompt(language: str, print_description: str, colors: str = '', style: str = '', shirt_color: str = '') -> str:
    template = load_text_prompt(language, 'title')
    return template.format(print_description=print_description, colors=colors, style=style, shirt_color=shirt_color)

"""Ollama 文本生成提供商"""
import json
import base64
from io import BytesIO
import httpx
from django.conf import settings
from .provider import AIProvider, AnalysisResult, TextResult


class OllamaProvider(AIProvider):
    """Ollama HTTP API 封装"""

    def __init__(self, base_url: str | None = None, model: str | None = None):
        self.base_url = base_url or settings.OLLAMA_BASE_URL
        self.model = model or settings.OLLAMA_MODEL
        self.client = httpx.Client(timeout=120.0)

    def generate_image(self, *args, **kwargs):
        raise NotImplementedError('Ollama does not support image generation')

    def analyze_image(self, image) -> AnalysisResult:
        buffered = BytesIO()
        image.save(buffered, format='PNG')
        img_base64 = base64.b64encode(buffered.getvalue()).decode()

        analysis_prompt = """Analyze this print/t-shirt design image. Return a JSON object with:
{
  "tags": ["style1", "style2", ...],
  "colors": ["#HEX1", "#HEX2", "#HEX3"],
  "description": "A concise description in English of the print pattern"
}
Only return the JSON, no other text."""

        resp = self.client.post(f'{self.base_url}/api/generate', json={
            'model': self.model,
            'prompt': analysis_prompt,
            'images': [img_base64],
            'stream': False,
        })
        resp.raise_for_status()

        result = resp.json()
        try:
            text = result['response'].strip()
            if text.startswith('```'):
                text = text.split('\n', 1)[1]
                if text.endswith('```'):
                    text = text[:-3]
            data = json.loads(text)
        except json.JSONDecodeError:
            data = {'tags': [], 'colors': [], 'description': result['response']}

        return AnalysisResult(
            tags=data.get('tags', []),
            colors=data.get('colors', []),
            description=data.get('description', ''),
        )

    def generate_text(self, prompt: str, language: str = 'id') -> TextResult:
        resp = self.client.post(f'{self.base_url}/api/generate', json={
            'model': self.model,
            'prompt': prompt,
            'stream': False,
        })
        resp.raise_for_status()

        result = resp.json()
        generated_text = result['response'].strip()

        lines = [line.strip() for line in generated_text.split('\n') if line.strip()]
        title = lines[0] if lines else ''
        description = '\n'.join(lines[1:]) if len(lines) > 1 else ''

        size_info = 'S, M, L, XL, XXL'

        return TextResult(
            title=title,
            description=description,
            size_info=size_info,
        )

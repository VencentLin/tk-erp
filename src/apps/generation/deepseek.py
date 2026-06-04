"""DeepSeek API 文本生成提供商"""
import json
import httpx
from django.conf import settings
from .provider import AIProvider, TextResult


class DeepSeekProvider(AIProvider):
    """DeepSeek V4 Flash API 封装（抖音 Coding Plan）"""

    def __init__(self, api_key: str | None = None, base_url: str | None = None,
                 model: str | None = None):
        self.api_key = api_key or settings.DEEPSEEK_API_KEY
        self.base_url = base_url or settings.DEEPSEEK_BASE_URL
        self.model = model or settings.DEEPSEEK_MODEL
        self.client = httpx.Client(timeout=120.0)

    def generate_image(self, *args, **kwargs):
        raise NotImplementedError('DeepSeek does not support image generation')

    def analyze_image(self, image):
        raise NotImplementedError('DeepSeek Flash does not support image analysis')

    def generate_text(self, prompt: str, language: str = 'id') -> TextResult:
        """使用 DeepSeek API 生成商品标题和描述"""
        resp = self.client.post(
            f'{self.base_url}/chat/completions',
            headers={
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'model': self.model,
                'messages': [
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.8,
                'max_tokens': 500,
            },
        )
        resp.raise_for_status()

        data = resp.json()
        generated_text = data['choices'][0]['message']['content'].strip()

        # 解析：第一行是标题，后续是描述
        lines = [line.strip() for line in generated_text.split('\n') if line.strip()]
        title = lines[0] if lines else ''
        description = '\n'.join(lines[1:]) if len(lines) > 1 else ''

        # 默认尺码
        size_info = 'S, M, L, XL, XXL'

        return TextResult(
            title=title,
            description=description,
            size_info=size_info,
        )

"""AI 提供商抽象接口"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ImageResult:
    """图像生成结果"""
    images: list  # list of PIL.Image
    metadata: dict = field(default_factory=dict)


@dataclass
class AnalysisResult:
    """图像分析结果"""
    tags: list[str] = field(default_factory=list)
    colors: list[str] = field(default_factory=list)
    description: str = ''


@dataclass
class TextResult:
    """文本生成结果"""
    title: str = ''
    description: str = ''
    size_info: str = ''


class AIProvider:
    """AI 提供商抽象基类"""

    def generate_image(self, prompt: str, reference_image=None,
                       params: dict | None = None) -> ImageResult:
        raise NotImplementedError

    def analyze_image(self, image) -> AnalysisResult:
        raise NotImplementedError

    def generate_text(self, prompt: str, language: str = 'id') -> TextResult:
        raise NotImplementedError

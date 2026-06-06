"""V7 CLIP Scoring + Validator System"""
import os
import io
import torch
import numpy as np
from PIL import Image
import threading

# Fix HuggingFace cache permission issue on Windows
_HF_CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), '.hf_cache')
os.makedirs(_HF_CACHE, exist_ok=True)
os.environ.setdefault('HF_HOME', _HF_CACHE)
os.environ.setdefault('TRANSFORMERS_CACHE', _HF_CACHE)

from transformers import CLIPProcessor, CLIPModel


class ClipScorer:
    """CLIP 单例 — 对生成图评分 + 审核"""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init_model()
        return cls._instance

    def _init_model(self):
        self.model = CLIPModel.from_pretrained('openai/clip-vit-base-patch32')
        self.processor = CLIPProcessor.from_pretrained('openai/clip-vit-base-patch32')
        self.model.eval()

    def score(self, image: Image.Image, text: str) -> float:
        """CLIP cosine similarity: image vs text. Returns 0-100 score."""
        inputs = self.processor(text=[text], images=image, return_tensors='pt', padding=True)
        with torch.no_grad():
            outputs = self.model(**inputs)
            similarity = outputs.logits_per_image[0][0].item()
        # Normalize to 0-100
        return max(0, min(100, (similarity + 1) * 50))

    def score_batch(self, images: list[Image.Image], text: str) -> list[float]:
        """Score multiple images against the same text."""
        return [self.score(img, text) for img in images]

    # ============================================================
    # V7 Validators
    # ============================================================

    def validate_garment(self, image: Image.Image) -> tuple[bool, float]:
        """Validator 1: 是否存在服装主体"""
        score = self.score(image, 'a t-shirt apparel product photo, garment visible')
        return score > 25, score

    def validate_print(self, image: Image.Image) -> tuple[bool, float]:
        """Validator 2: 是否存在印花"""
        score = self.score(image, 'a t-shirt with graphic print design on it')
        return score > 25, score

    def validate_no_human(self, image: Image.Image) -> tuple[bool, float]:
        """Validator 3: 是否无人物"""
        score = self.score(image, 'a person, human, model, face, portrait')
        # Low score = no human (good), so we invert
        return score < 22, 100 - score

    def validate_product_photo(self, image: Image.Image) -> tuple[bool, float]:
        """Validator 4: 是否为商品图（非海报/插图/浮空印花）"""
        product_score = self.score(image, 'ecommerce product photo, taobao clothing listing')
        artwork_score = self.score(image, 'standalone artwork, poster, illustration, canvas')
        is_product = product_score > artwork_score
        return is_product, product_score - artwork_score

    # ============================================================
    # Combined scoring
    # ============================================================

    def evaluate(self, image: Image.Image, prompt: str) -> dict:
        """综合评分：CLIP + 4 validators → 总分"""
        clip_score = self.score(image, prompt)

        v1_pass, v1_score = self.validate_garment(image)
        v2_pass, v2_score = self.validate_print(image)
        v3_pass, v3_score = self.validate_no_human(image)
        v4_pass, v4_score = self.validate_product_photo(image)

        validator_pass = sum([v1_pass, v2_pass, v3_pass, v4_pass])

        # 综合分：CLIP (60%) + Validator avg (40%)，validators 全过则加权
        validator_avg = (v1_score + v2_score + v3_score + v4_score) / 4
        combined = clip_score * 0.6 + validator_avg * 0.4

        # 如果任何 validator 失败，减分
        if validator_pass < 4:
            combined *= (0.5 + 0.125 * validator_pass)  # 0.625, 0.75, 0.875, 1.0

        return {
            'clip_score': round(clip_score, 1),
            'combined_score': round(combined, 1),
            'validator_pass': validator_pass,
            'details': {
                'garment': (v1_pass, round(v1_score, 1)),
                'print': (v2_pass, round(v2_score, 1)),
                'no_human': (v3_pass, round(v3_score, 1)),
                'product_photo': (v4_pass, round(v4_score, 1)),
            }
        }

    def select_best(self, images: list[Image.Image], prompt: str) -> tuple[Image.Image, dict]:
        """从 4 张候选图中选出最佳"""
        if not images:
            return None, {}
        results = [self.evaluate(img, prompt) for img in images]
        best_idx = max(range(len(results)), key=lambda i: results[i]['combined_score'])
        return images[best_idx], results[best_idx]

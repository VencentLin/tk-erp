"""ComfyUI 图像生成提供商"""
import json
import time
import httpx
from io import BytesIO
from typing import Any
from PIL import Image
from django.conf import settings
from .provider import AIProvider, ImageResult


def _load_model_config() -> str:
    """加载用户选择的模型，优先配置文件 > settings"""
    import json
    from pathlib import Path
    config_path = Path(__file__).resolve().parent.parent.parent.parent / 'data' / 'config.json'
    try:
        if config_path.exists():
            with open(config_path) as f:
                data = json.load(f)
            return data.get('comfyui_model', settings.COMFYUI_MODEL)
    except Exception:
        pass
    return getattr(settings, 'COMFYUI_MODEL', 'sd_xl_base_1.0_0.9vae.safetensors')


class ComfyUIProvider(AIProvider):
    """ComfyUI HTTP API 封装"""

    def __init__(self, base_url: str | None = None, model: str | None = None):
        self.base_url = base_url or settings.COMFYUI_BASE_URL
        self.model = model or _load_model_config()
        self.client = httpx.Client(timeout=120.0)
        self.client_id = str(__import__('uuid').uuid4())

    def get_available_checkpoints(self) -> list[str]:
        """获取 ComfyUI 中可用的模型列表"""
        try:
            resp = self.client.get(f'{self.base_url}/object_info/CheckpointLoaderSimple')
            resp.raise_for_status()
            data = resp.json()
            return list(data['CheckpointLoaderSimple']['input']['required']['ckpt_name'][0])
        except Exception:
            return [self.model]

    def _upload_image(self, image: Image) -> str:
        """上传图片到 ComfyUI，返回上传后的文件名"""
        import io as io_mod
        buf = io_mod.BytesIO()
        image.save(buf, format='PNG')
        buf.seek(0)

        resp = self.client.post(
            f'{self.base_url}/upload/image',
            files={'image': ('reference.png', buf, 'image/png')},
        )
        resp.raise_for_status()
        return resp.json()['name']

    def generate_image(self, prompt: str, reference_image=None,
                       params: dict | None = None) -> ImageResult:
        params = params or {}
        workflow = self._build_workflow(prompt, reference_image, params)
        prompt_id = self._queue_prompt(workflow)
        images_data = self._wait_for_result(prompt_id)

        generated = [Image.open(BytesIO(data)) for data in images_data]
        return ImageResult(
            images=generated,
            metadata={'prompt_id': prompt_id, 'node_id': 'output'}
        )

    def _build_workflow(self, prompt: str, reference_image, params: dict) -> dict:
        if reference_image:
            # img2img: 上传参考图 → VAE编码 → KSampler使用denoise<1
            return self._build_img2img_workflow(prompt, reference_image, params)
        else:
            return self._build_txt2img_workflow(prompt, params)

    def _build_img2img_workflow(self, prompt: str, reference_image: Image, params: dict) -> dict:
        uploaded_name = self._upload_image(reference_image)
        seed = params.get('seed', 0)
        steps = params.get('steps', 25)
        cfg = params.get('cfg_scale', 7.0)
        denoise = params.get('denoising_strength', 0.65)

        return {
            "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": self.model}},
            "2": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": prompt}, "_meta": {"title": "Positive Prompt"}},
            "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": "photo, realistic, human, face, text, watermark, logo, blurry, low quality, messy edges, distorted"}, "_meta": {"title": "Negative Prompt"}},
            "4": {"class_type": "LoadImage", "inputs": {"image": uploaded_name}},
            "5": {"class_type": "VAEEncode", "inputs": {"pixels": ["4", 0], "vae": ["1", 2]}},
            "6": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["5", 0], "seed": seed, "steps": steps, "cfg": cfg, "sampler_name": "euler", "scheduler": "normal", "denoise": denoise}},
            "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["1", 2]}},
            "8": {"class_type": "SaveImage", "inputs": {"filename_prefix": "print_variant", "images": ["7", 0]}},
        }

    def _build_txt2img_workflow(self, prompt: str, params: dict) -> dict:
        seed = params.get('seed', 0)
        steps = params.get('steps', 25)
        cfg = params.get('cfg_scale', 7.0)
        width = params.get('width', 1024)
        height = params.get('height', 1024)

        return {
            "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": self.model}},
            "2": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": prompt}, "_meta": {"title": "Positive Prompt"}},
            "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": "photo, realistic, human, face, text, watermark, logo, blurry, low quality, messy edges"}, "_meta": {"title": "Negative Prompt"}},
            "4": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
            "5": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0], "seed": seed, "steps": steps, "cfg": cfg, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0}},
            "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
            "7": {"class_type": "SaveImage", "inputs": {"filename_prefix": "print_variant", "images": ["6", 0]}},
        }

    def _queue_prompt(self, workflow: dict) -> str:
        resp = self.client.post(f'{self.base_url}/prompt', json={
            'prompt': workflow,
            'client_id': self.client_id,
        })
        resp.raise_for_status()
        return resp.json()['prompt_id']

    def _wait_for_result(self, prompt_id: str, poll_interval: float = 2.0,
                         max_wait: float = 300.0) -> list[bytes]:
        elapsed = 0.0
        while elapsed < max_wait:
            time.sleep(poll_interval)
            elapsed += poll_interval
            try:
                resp = self.client.get(f'{self.base_url}/history/{prompt_id}')
                resp.raise_for_status()
                data = resp.json()
                if prompt_id in data:
                    history = data[prompt_id]
                    images = []
                    for node_id, node_output in history.get('outputs', {}).items():
                        for img_info in node_output.get('images', []):
                            img_resp = self.client.get(
                                f'{self.base_url}/view',
                                params={
                                    'filename': img_info['filename'],
                                    'subfolder': img_info.get('subfolder', ''),
                                    'type': img_info.get('type', 'output'),
                                }
                            )
                            img_resp.raise_for_status()
                            images.append(img_resp.content)
                    if images:
                        return images
            except httpx.HTTPError:
                continue

        raise TimeoutError(f'ComfyUI generation timed out after {max_wait}s')

    def analyze_image(self, image) -> Any:
        raise NotImplementedError('ComfyUI does not support image analysis')

    def generate_text(self, prompt: str, language: str = 'id') -> Any:
        raise NotImplementedError('ComfyUI does not support text generation')

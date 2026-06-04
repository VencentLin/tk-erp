"""ComfyUI 图像生成提供商"""
import json
import time
import httpx
from io import BytesIO
from typing import Any
from PIL import Image
from django.conf import settings
from .provider import AIProvider, ImageResult


class ComfyUIProvider(AIProvider):
    """ComfyUI HTTP API 封装"""

    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or settings.COMFYUI_BASE_URL
        self.client = httpx.Client(timeout=120.0)

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
        import json
        from pathlib import Path

        workflow_path = (
            Path(__file__).resolve().parent.parent.parent.parent
            / 'ai' / 'comfy_workflows' / 'print_variation.json'
        )

        if workflow_path.exists():
            with open(workflow_path) as f:
                workflow = json.load(f)
        else:
            workflow = self._default_workflow()

        for node_id, node in workflow.items():
            if node.get('class_type') == 'CLIPTextEncode':
                if node.get('_meta', {}).get('title') == 'Positive Prompt':
                    node['inputs']['text'] = prompt
            if node.get('class_type') == 'KSampler':
                node['inputs']['steps'] = params.get('steps', 30)
                node['inputs']['cfg'] = params.get('cfg_scale', 7.0)
                if 'denoising' in params:
                    node['inputs']['denoise'] = params['denoising']

        return workflow

    def _default_workflow(self) -> dict:
        return {
            "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"}},
            "2": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": ""}, "_meta": {"title": "Positive Prompt"}},
            "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": ""}, "_meta": {"title": "Negative Prompt"}},
            "4": {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 1024, "batch_size": 4}},
            "5": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0], "seed": 0, "steps": 30, "cfg": 7.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0}},
            "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
            "7": {"class_type": "SaveImage", "inputs": {"filename_prefix": "print_variant", "images": ["6", 0]}},
        }

    def _queue_prompt(self, workflow: dict) -> str:
        resp = self.client.post(f'{self.base_url}/prompt', json={'prompt': workflow})
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

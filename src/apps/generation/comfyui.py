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
    return getattr(settings, 'COMFYUI_MODEL', 'juggernautXL_v9Rundiffusionphoto2.safetensors')


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
            "6": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["5", 0], "seed": seed, "steps": steps, "cfg": cfg, "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": denoise}},
            "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["1", 2]}},
            "8": {"class_type": "SaveImage", "inputs": {"filename_prefix": "print_variant", "images": ["7", 0]}},
        }

    def _build_txt2img_workflow(self, prompt: str, params: dict) -> dict:
        seed = params.get('seed', 0)
        steps = params.get('steps', 25)
        cfg = params.get('cfg_scale', 7.0)
        width = params.get('width', 1024)
        height = params.get('height', 1024)
        neg_prompt = params.get('negative_prompt', 'photo, realistic, human, face, text, watermark, logo, blurry, low quality, messy edges')

        return {
            "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": self.model}},
            "2": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": prompt}, "_meta": {"title": "Positive Prompt"}},
            "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": neg_prompt}, "_meta": {"title": "Negative Prompt"}},
            "4": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
            "5": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0], "seed": seed, "steps": steps, "cfg": cfg, "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 1.0}},
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

    # ============================================================
    # POD Methods
    # ============================================================

    def _load_pod_config(self) -> dict:
        """加载 POD 印花生成配置"""
        import json as _json
        config_path = __import__('pathlib').Path(__file__).resolve().parent.parent.parent.parent / 'data' / 'config.json'
        defaults = {
            'print_checkpoint': 'sd_xl_turbo_1.0_bf16.safetensors',
            'print_lora_name': '',
            'print_lora_strength_model': 0.8,
            'print_lora_strength_clip': 0.8,
        }
        try:
            if config_path.exists():
                with open(config_path) as f:
                    data = _json.load(f)
                for k in defaults:
                    if k in data:
                        defaults[k] = data[k]
        except Exception:
            pass
        return defaults

    def generate_print_design(self, prompt: str, params: dict | None = None) -> ImageResult:
        """POD 印花生成 — 支持可选 LoRA"""
        params = params or {}
        pod_config = self._load_pod_config()
        checkpoint = pod_config['print_checkpoint']
        lora_name = pod_config['print_lora_name']
        lora_strength_model = pod_config['print_lora_strength_model']
        lora_strength_clip = pod_config['print_lora_strength_clip']

        seed = params.get('seed', 0)
        steps = params.get('steps', 1)  # Turbo: 1 step
        cfg = params.get('cfg_scale', 1.0)  # Turbo: cfg 1.0
        width = params.get('width', 1024)
        height = params.get('height', 1024)
        neg_prompt = params.get('negative_prompt', 'text, letters, photo, realistic, human, face, body, logo, watermark')

        workflow = {}
        node_id = 1

        # Node 1: CheckpointLoader
        workflow[str(node_id)] = {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint}}
        ckpt_node = node_id
        node_id += 1

        # Node 2-3: CLIP connections
        clip_ref = [str(ckpt_node), 1]
        model_ref = [str(ckpt_node), 0]
        vae_ref = [str(ckpt_node), 2]

        # Optional LoraLoader
        if lora_name:
            workflow[str(node_id)] = {
                "class_type": "LoraLoader",
                "inputs": {
                    "model": model_ref,
                    "clip": clip_ref,
                    "lora_name": lora_name,
                    "strength_model": lora_strength_model,
                    "strength_clip": lora_strength_clip,
                }
            }
            lora_node = node_id
            node_id += 1
            model_ref = [str(lora_node), 0]
            clip_ref = [str(lora_node), 1]

        # Positive encode
        workflow[str(node_id)] = {"class_type": "CLIPTextEncode", "inputs": {"clip": clip_ref, "text": prompt},
                                  "_meta": {"title": "Positive Prompt"}}
        pos_node = node_id
        node_id += 1

        # Negative encode
        workflow[str(node_id)] = {"class_type": "CLIPTextEncode", "inputs": {"clip": clip_ref, "text": neg_prompt},
                                  "_meta": {"title": "Negative Prompt"}}
        neg_node = node_id
        node_id += 1

        # EmptyLatentImage
        workflow[str(node_id)] = {"class_type": "EmptyLatentImage",
                                  "inputs": {"width": width, "height": height, "batch_size": 1}}
        latent_node = node_id
        node_id += 1

        # KSampler
        workflow[str(node_id)] = {"class_type": "KSampler",
                                  "inputs": {"model": model_ref, "positive": [str(pos_node), 0],
                                             "negative": [str(neg_node), 0], "latent_image": [str(latent_node), 0],
                                             "seed": seed, "steps": steps, "cfg": cfg,
                                             "sampler_name": params.get('sampler_name', 'euler'),
                                             "scheduler": params.get('scheduler', 'sgm_uniform'), "denoise": 1.0}}
        sampler_node = node_id
        node_id += 1

        # VAEDecode
        workflow[str(node_id)] = {"class_type": "VAEDecode",
                                  "inputs": {"samples": [str(sampler_node), 0], "vae": vae_ref}}
        decode_node = node_id
        node_id += 1

        # SaveImage
        workflow[str(node_id)] = {"class_type": "SaveImage",
                                  "inputs": {"filename_prefix": "pod_print", "images": [str(decode_node), 0]}}

        prompt_id = self._queue_prompt(workflow)
        images_data = self._wait_for_result(prompt_id)
        generated = [Image.open(BytesIO(data)) for data in images_data]
        return ImageResult(images=generated, metadata={'prompt_id': prompt_id, 'workflow': 'pod_print'})

    def remove_print_background(self, image: Image) -> ImageResult:
        """去背景 — 尝试 RMBG 节点，不可用时返回原始图（前端需提示用户）"""
        try:
            uploaded_name = self._upload_image(image)

            workflow = {
                "1": {"class_type": "LoadImage", "inputs": {"image": uploaded_name}},
                "2": {"class_type": "Image Remove Background (RMBG)",
                      "inputs": {"images": ["1", 0]}},
                "3": {"class_type": "SaveImage",
                      "inputs": {"filename_prefix": "pod_transparent", "images": ["2", 0]}},
            }

            prompt_id = self._queue_prompt(workflow)
            images_data = self._wait_for_result(prompt_id, max_wait=120.0)
            if images_data:
                return ImageResult(
                    images=[Image.open(BytesIO(data)) for data in images_data],
                    metadata={'method': 'rmbg'}
                )
        except Exception as e:
            # RMBG not available — try white bg alpha approach
            pass

        # Fallback: return original image (caller should check and warn)
        return ImageResult(
            images=[image],
            metadata={'method': 'passthrough', 'warning': 'RMBG node not available, install rgthree or similar'}
        )

    def composite_pod_image(self, template_image: Image, print_image: Image,
                            x: int, y: int, width: int, height: int) -> ImageResult:
        """将印花合成到模板图的指定区域"""
        # Upload both images
        template_name = self._upload_image(template_image)
        print_name = self._upload_image(print_image)

        workflow = {
            "1": {"class_type": "LoadImage", "inputs": {"image": template_name}},
            "2": {"class_type": "LoadImage", "inputs": {"image": print_name}},
            # Resize print to target size (use built-in ImageScale)
            "3": {"class_type": "ImageScale",
                  "inputs": {"image": ["2", 0], "width": width, "height": height,
                             "upscale_method": "lanczos", "crop": "disabled"}},
            # Create mask from resized print (use alpha or full white mask)
            "4": {"class_type": "SolidMask",
                  "inputs": {"value": 1.0, "width": width, "height": height}},
            # Composite: paste print onto template at (x, y)
            "5": {"class_type": "ImageCompositeMasked",
                  "inputs": {"destination": ["1", 0], "source": ["3", 0],
                             "x": x, "y": y, "mask": ["4", 0]}},
            "6": {"class_type": "SaveImage",
                  "inputs": {"filename_prefix": "pod_composite", "images": ["5", 0]}},
        }

        prompt_id = self._queue_prompt(workflow)
        images_data = self._wait_for_result(prompt_id)
        generated = [Image.open(BytesIO(data)) for data in images_data]
        return ImageResult(images=generated, metadata={'prompt_id': prompt_id, 'workflow': 'pod_composite'})

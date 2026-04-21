"""
ComfyUI API client for SD 1.5 + Hyper-SD 1-step image generation.
Connects via WebSocket for progress updates and step previews.
"""

import json
import urllib.request
import urllib.parse
import io
import uuid

COMFYUI_URL = "http://127.0.0.1:8188"
CLIENT_ID = str(uuid.uuid4())

# SD 1.5 + Hyper-SD 1-step LoRA workflow
WORKFLOW_TEMPLATE = {
    "3": {
        "class_type": "KSampler",
        "inputs": {
            "seed": 0,
            "steps": 1,
            "cfg": 1.0,
            "sampler_name": "euler",
            "scheduler": "normal",
            "denoise": 1.0,
            "model": ["10", 0],
            "positive": ["6", 0],
            "negative": ["7", 0],
            "latent_image": ["5", 0],
        },
    },
    "4": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {
            "ckpt_name": "v1-5-pruned-emaonly-fp16.safetensors",
        },
    },
    "5": {
        "class_type": "EmptyLatentImage",
        "inputs": {
            "width": 512,
            "height": 512,
            "batch_size": 1,
        },
    },
    "6": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": "",
            "clip": ["10", 1],
        },
    },
    "7": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": "blurry, ugly, deformed, text, watermark, low quality",
            "clip": ["10", 1],
        },
    },
    "8": {
        "class_type": "VAEDecode",
        "inputs": {
            "samples": ["3", 0],
            "vae": ["4", 2],
        },
    },
    "9": {
        "class_type": "SaveImage",
        "inputs": {
            "filename_prefix": "narrate",
            "images": ["8", 0],
        },
    },
    "10": {
        "class_type": "LoraLoader",
        "inputs": {
            "lora_name": "Hyper-SD15-1step-lora.safetensors",
            "strength_model": 1.0,
            "strength_clip": 1.0,
            "model": ["4", 0],
            "clip": ["4", 1],
        },
    },
}


def queue_prompt(prompt_text: str, seed: int | None = None) -> str:
    """Queue an image generation with the given prompt. Returns prompt_id."""
    import random

    workflow = json.loads(json.dumps(WORKFLOW_TEMPLATE))
    workflow["6"]["inputs"]["text"] = prompt_text
    workflow["3"]["inputs"]["seed"] = seed if seed is not None else random.randint(0, 2**32)

    payload = {
        "prompt": workflow,
        "client_id": CLIENT_ID,
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{COMFYUI_URL}/prompt",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
        return result["prompt_id"]


def get_image(prompt_id: str) -> bytes | None:
    """Poll for the completed image. Returns image bytes or None."""
    with urllib.request.urlopen(f"{COMFYUI_URL}/history/{prompt_id}") as resp:
        history = json.loads(resp.read())

    if prompt_id not in history:
        return None

    outputs = history[prompt_id].get("outputs", {})
    for node_id, node_output in outputs.items():
        if "images" in node_output:
            img_info = node_output["images"][0]
            img_url = (
                f"{COMFYUI_URL}/view?"
                f"filename={urllib.parse.quote(img_info['filename'])}"
                f"&subfolder={urllib.parse.quote(img_info.get('subfolder', ''))}"
                f"&type={urllib.parse.quote(img_info.get('type', 'output'))}"
            )
            with urllib.request.urlopen(img_url) as img_resp:
                return img_resp.read()
    return None


def connect_websocket():
    """
    Connect to ComfyUI WebSocket for real-time progress and preview images.
    Returns a websocket connection.
    """
    import websocket

    ws = websocket.WebSocket()
    ws.connect(f"ws://127.0.0.1:8188/ws?clientId={CLIENT_ID}")
    return ws


def generate_with_progress(prompt_text: str, on_preview=None, on_progress=None, seed=None):
    """
    Generate an image with real-time progress callbacks.

    on_preview(image_bytes): called when a step preview is available
    on_progress(step, total_steps): called on each step

    Returns final image bytes.
    """
    import websocket
    import struct

    ws = connect_websocket()
    prompt_id = queue_prompt(prompt_text, seed=seed)

    try:
        while True:
            msg = ws.recv()

            if isinstance(msg, bytes):
                # Binary message: preview image
                # First 8 bytes: type (4) + format (4), rest is image data
                if len(msg) > 8 and on_preview:
                    on_preview(msg[8:])
                continue

            data = json.loads(msg)
            msg_type = data.get("type")

            if msg_type == "progress":
                step = data["data"]["value"]
                total = data["data"]["max"]
                if on_progress:
                    on_progress(step, total)

            elif msg_type == "executing":
                if data["data"]["node"] is None and data["data"]["prompt_id"] == prompt_id:
                    # Generation complete
                    break

    finally:
        ws.close()

    return get_image(prompt_id)


def is_comfyui_running() -> bool:
    """Check if ComfyUI server is reachable."""
    try:
        with urllib.request.urlopen(f"{COMFYUI_URL}/system_stats", timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False

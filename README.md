# NarrateVision

Speak or read aloud and watch scenes illustrated in real-time. Fully local on Apple Silicon.

## Architecture

```
Browser mic (Web Speech API) → WebSocket → Scene Extractor → ComfyUI API (SD 1.5 + Hyper-SD) → Browser display
```

## Requirements

- macOS with Apple Silicon (M1 Pro 32GB tested)
- Python 3.10+
- ComfyUI running locally
- Chrome or Edge (for Web Speech API)

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Download models into ComfyUI:
```bash
# SD 1.5 checkpoint (2.1GB)
cd /path/to/ComfyUI/models/checkpoints/
curl -L -o v1-5-pruned-emaonly-fp16.safetensors \
  "https://huggingface.co/Comfy-Org/stable-diffusion-v1-5-archive/resolve/main/v1-5-pruned-emaonly-fp16.safetensors"

# Hyper-SD 1-step LoRA (257MB)
cd /path/to/ComfyUI/models/loras/
curl -L -o Hyper-SD15-1step-lora.safetensors \
  "https://huggingface.co/ByteDance/Hyper-SD/resolve/main/Hyper-SD15-1step-lora.safetensors"
```

## Usage

1. Start ComfyUI:
   ```
   cd /path/to/ComfyUI && python3 main.py
   ```

2. Start NarrateVision:
   ```
   source venv/bin/activate
   python3 server.py
   ```

3. Open http://localhost:8765 in Chrome/Edge

4. Click "Start Listening" and read aloud. Click "Read a Story" for a built-in story to read.

## How it works

1. Browser captures speech via Web Speech API (no server-side audio processing needed)
2. Transcripts are sent over WebSocket to the Python server
3. Scene extractor picks out visual keywords (characters, settings, atmosphere)
4. ComfyUI generates a storybook-style illustration using SD 1.5 + Hyper-SD (1 step, ~2-4 seconds)
5. Image streams back to the browser with a fade-in transition

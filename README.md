# NarrateVision

Speak or read aloud and watch scenes illustrated in real-time. Fully local on Apple Silicon.

## Architecture

```
Mic → mlx-whisper (real-time STT) → Scene Extractor → ComfyUI API (SDXL Lightning) → Display
```

## Requirements

- macOS with Apple Silicon (M1 Pro 32GB tested)
- Python 3.10+
- ComfyUI running locally with SDXL Lightning checkpoint
- LM Studio with a small model for scene extraction (optional, falls back to keyword extraction)

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Download SDXL Lightning 4-step checkpoint into ComfyUI:
```bash
cd /Volumes/X9Pro/Developer/ComfyUI/models/checkpoints/
curl -L -o sdxl_lightning_4step.safetensors \
  "https://huggingface.co/ByteDance/SDXL-Lightning/resolve/main/sdxl_lightning_4step.safetensors"
```

Start ComfyUI, then run:
```bash
python3 narrate.py
```

## How it works

1. Listens to your microphone in real-time
2. Transcribes speech using mlx-whisper (on-device, no cloud)
3. Extracts scene descriptions from transcript chunks
4. Sends prompts to ComfyUI's API for SDXL Lightning image generation
5. Displays illustrations in a window as you speak

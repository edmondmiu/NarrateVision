# NarrateVision

Speak or read aloud and watch scenes illustrated in real-time. Fully local on Apple Silicon — no cloud APIs, no data leaves your machine.

Designed for reading stories to kids: one person narrates, the screen fills with storybook illustrations that update as the scene changes.

## How it works

```
Browser mic (Web Speech API)
        ↓  WebSocket
  Python server (FastAPI)
        ↓  extract visual keywords
  Scene extractor
        ↓  prompt
  ComfyUI (SD 1.5 + Hyper-SD 1-step LoRA)
        ↓  512x512 PNG
  Browser display (fade-in)
```

1. Chrome captures speech via the Web Speech API (transcription happens in the browser, zero server-side audio processing).
2. Transcripts stream over a WebSocket to the Python server.
3. A scene extractor picks out characters, settings, and atmosphere from the rolling transcript.
4. ComfyUI generates a storybook-style illustration in a single diffusion step (~2-4 seconds on M1 Pro).
5. The image streams back to the browser and fades in.

## Requirements

- macOS with Apple Silicon (tested on M1 Pro, 32GB)
- Python 3.10+
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) installed and runnable
- Chrome or Edge (Web Speech API is not available in Safari or Firefox)

## Setup

### 1. Install NarrateVision

```bash
git clone https://github.com/edmondmiu/NarrateVision.git
cd NarrateVision
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Download models into ComfyUI

SD 1.5 base checkpoint (2.1GB):

```bash
cd /path/to/ComfyUI/models/checkpoints/
curl -L -o v1-5-pruned-emaonly-fp16.safetensors \
  "https://huggingface.co/Comfy-Org/stable-diffusion-v1-5-archive/resolve/main/v1-5-pruned-emaonly-fp16.safetensors"
```

Hyper-SD 1-step LoRA (257MB):

```bash
cd /path/to/ComfyUI/models/loras/
curl -L -o Hyper-SD15-1step-lora.safetensors \
  "https://huggingface.co/ByteDance/Hyper-SD/resolve/main/Hyper-SD15-1step-lora.safetensors"
```

## Usage

1. Start ComfyUI:

   ```bash
   cd /path/to/ComfyUI
   python3 main.py
   ```

2. In a separate terminal, start NarrateVision:

   ```bash
   cd NarrateVision
   source venv/bin/activate
   python3 server.py
   ```

3. Open `http://localhost:8765` in Chrome or Edge.

4. Click **Start Listening** and begin reading aloud. Or click **Read a Story** for a built-in sample.

5. When you're done, click **Unload** to free GPU memory.

## Project layout

| File | Purpose |
|---|---|
| `server.py` | FastAPI server: serves the UI and handles WebSocket transcripts |
| `narrate.py` | Standalone desktop mode using PyQt + mlx-whisper (alternative to browser) |
| `comfyui_client.py` | Talks to ComfyUI over HTTP + WebSocket, builds the workflow JSON |
| `scene_extractor.py` | Picks visual keywords from the rolling transcript |
| `static/index.html` | Browser UI (mic capture, image strip, controls) |
| `launch.command` | Double-click launcher for macOS |

## Model choice

The current setup uses **SD 1.5 + Hyper-SD 1-step LoRA at 512x512**. This was chosen for speed on an M1 Pro: generation lands around 2-4 seconds per scene, which is short enough to keep up with natural narration pace. Previous iterations used SDXL Lightning (4-step, slower) — see the git history if you want to switch back for higher fidelity at the cost of latency.

## Troubleshooting

**"ComfyUI not running"**
Make sure ComfyUI is listening on `127.0.0.1:8188` (the default). Check with `curl http://127.0.0.1:8188/system_stats`.

**Browser mic not working**
Web Speech API only runs in Chrome and Edge. Safari and Firefox will not work. Also check that the site has microphone permission.

**First image is slow**
The first generation loads the model into VRAM (~10-15s). Subsequent images are ~2-4s. Click **Unload** when you're done to free memory.

**Weird or unrelated illustrations**
The scene extractor is keyword-based, not LLM-driven — it works best with vivid, concrete language. Abstract narration ("then he thought about life") will produce vague images.

## License

Personal project, no license declared. Ask before reusing.

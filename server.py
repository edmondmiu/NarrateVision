#!/usr/bin/env python3
"""
NarrateVision web server.
Serves the UI and handles audio transcription + image generation via WebSocket.
"""

import asyncio
import base64
import json
import subprocess
import sys
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from scene_extractor import extract_scene_from_accumulator
from comfyui_client import generate_with_progress, is_comfyui_running, queue_prompt, get_image

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

MIN_WORDS_FOR_SCENE = 8
SCENE_COOLDOWN = 5.0

# Track warm-up state
warmup_state = {"ready": False, "status": "idle"}


@app.get("/")
async def index():
    with open("static/index.html") as f:
        return HTMLResponse(f.read())


@app.get("/status")
async def status():
    return {
        "comfyui": is_comfyui_running(),
        "warmed_up": warmup_state["ready"],
        "warmup_status": warmup_state["status"],
    }


@app.post("/warmup")
async def warmup():
    """Load models into GPU memory by running a throwaway generation."""
    if warmup_state["ready"]:
        return {"status": "already_ready"}

    if warmup_state["status"] == "warming":
        return {"status": "in_progress"}

    warmup_state["status"] = "warming"

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _do_warmup)

    return {"status": "ready" if warmup_state["ready"] else "failed"}


def _do_warmup():
    """Run a single throwaway generation to load checkpoint + LoRA into memory."""
    try:
        print("[warmup] Loading models into memory...")
        image_bytes = generate_with_progress("a simple red circle on white background")
        if image_bytes:
            warmup_state["ready"] = True
            warmup_state["status"] = "ready"
            print("[warmup] Models loaded. Ready to go.")
        else:
            warmup_state["status"] = "failed"
            print("[warmup] Generation returned no image.")
    except Exception as e:
        warmup_state["status"] = "failed"
        print(f"[warmup] Error: {e}")


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()

    sentences = []
    last_prompt = None
    last_gen_time = 0
    generating = False

    try:
        while True:
            data = await ws.receive_json()

            if data["type"] == "transcript":
                text = data["text"].strip()
                if not text or len(text.split()) < 3:
                    continue

                sentences.append(text)
                await ws.send_json({"type": "transcript", "text": text})

                # Check cooldown
                elapsed = time.time() - last_gen_time
                if elapsed < SCENE_COOLDOWN or generating:
                    continue

                # Extract scene
                prompt = extract_scene_from_accumulator(sentences, last_prompt)
                if not prompt:
                    continue

                total_words = sum(len(s.split()) for s in sentences[-3:])
                if total_words < MIN_WORDS_FOR_SCENE:
                    continue

                generating = True
                last_prompt = prompt
                last_gen_time = time.time()

                await ws.send_json({"type": "status", "text": f"Illustrating: {prompt[:60]}..."})

                loop = asyncio.get_event_loop()
                image_bytes = await loop.run_in_executor(
                    None, _generate_image, prompt
                )

                if image_bytes:
                    b64 = base64.b64encode(image_bytes).decode("utf-8")
                    await ws.send_json({"type": "image", "data": b64, "prompt": prompt})
                    await ws.send_json({"type": "status", "text": "Listening... Keep reading."})

                generating = False

    except WebSocketDisconnect:
        pass


def _generate_image(prompt: str) -> bytes | None:
    """Generate an image synchronously (runs in thread pool)."""
    try:
        return generate_with_progress(prompt)
    except Exception as e:
        print(f"[gen] Error: {e}")
        return None


def _start_comfyui():
    """Attempt to start ComfyUI in the background."""
    import os

    comfyui_path = os.environ.get(
        "COMFYUI_PATH", "/Volumes/X9Pro/Developer/ComfyUI"
    )
    main_py = os.path.join(comfyui_path, "main.py")

    if not os.path.exists(main_py):
        print(f"[comfyui] Not found at {comfyui_path}")
        return False

    print(f"[comfyui] Starting from {comfyui_path}...")
    subprocess.Popen(
        [sys.executable, main_py, "--listen", "127.0.0.1", "--port", "8188"],
        cwd=comfyui_path,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for it to come up
    for _ in range(30):
        time.sleep(2)
        if is_comfyui_running():
            print("[comfyui] Running.")
            return True

    print("[comfyui] Failed to start within 60 seconds.")
    return False


if __name__ == "__main__":
    import uvicorn

    if not is_comfyui_running():
        print("[comfyui] Not running. Attempting to start it...")
        if not _start_comfyui():
            print(
                "\n[error] Could not start ComfyUI automatically."
                "\n        Start it manually: cd /Volumes/X9Pro/Developer/ComfyUI && python3 main.py"
                "\n        Then run this script again.\n"
            )
            exit(1)

    print("\nNarrateVision")
    print("=============")
    print("Open http://localhost:8765 in your browser\n")
    uvicorn.run(app, host="0.0.0.0", port=8765)

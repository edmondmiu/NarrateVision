#!/usr/bin/env python3
"""
NarrateVision web server.
Serves the UI and handles audio transcription + image generation via WebSocket.
"""

import asyncio
import base64
import io
import json
import time
import tempfile

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from scene_extractor import extract_scene_from_accumulator
from comfyui_client import generate_with_progress, is_comfyui_running

app = FastAPI()

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# State per connection
MIN_WORDS_FOR_SCENE = 8
SCENE_COOLDOWN = 5.0


@app.get("/")
async def index():
    with open("static/index.html") as f:
        return HTMLResponse(f.read())


@app.get("/status")
async def status():
    return {"comfyui": is_comfyui_running()}


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

                # Run generation in thread to avoid blocking
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


if __name__ == "__main__":
    import uvicorn

    if not is_comfyui_running():
        print(
            "\n[error] ComfyUI is not running."
            "\n        Start it first: cd /Volumes/X9Pro/Developer/ComfyUI && python3 main.py"
            "\n        Then run this script again.\n"
        )
        exit(1)

    print("\nNarrateVision")
    print("=============")
    print("Open http://localhost:8765 in your browser\n")
    uvicorn.run(app, host="0.0.0.0", port=8765)

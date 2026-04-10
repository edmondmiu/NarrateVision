#!/usr/bin/env python3
"""
NarrateVision: Speak or read aloud and watch scenes illustrated in real-time.
Fully local on Apple Silicon.

Usage:
    python3 narrate.py

Press Ctrl+C to stop.
"""

import sys
import threading
import queue
import time
import io
import signal

import numpy as np
import sounddevice as sd
from PIL import Image

from scene_extractor import extract_scene_from_accumulator
from comfyui_client import generate_with_progress, is_comfyui_running

# Audio config for mlx-whisper
SAMPLE_RATE = 16000
CHUNK_DURATION = 3  # seconds of audio per transcription chunk
SILENCE_THRESHOLD = 0.01  # RMS below this = silence

# Scene config
MIN_WORDS_FOR_SCENE = 8  # need enough words to extract a meaningful scene
SCENE_COOLDOWN = 5.0  # minimum seconds between image generations


class TranscriptionWorker:
    """Records audio and transcribes in real-time using mlx-whisper."""

    def __init__(self, text_queue: queue.Queue):
        self.text_queue = text_queue
        self.running = False
        self.audio_buffer = []

    def start(self):
        import mlx_whisper

        self.running = True
        self.model = "mlx-community/whisper-small-mlx"

        print("[mic] Listening... Speak or read aloud.")

        def audio_callback(indata, frames, time_info, status):
            if status:
                print(f"[mic] {status}", file=sys.stderr)
            self.audio_buffer.extend(indata[:, 0].copy())

        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocksize=int(SAMPLE_RATE * 0.5),
            callback=audio_callback,
        )
        self.stream.start()

        while self.running:
            time.sleep(CHUNK_DURATION)

            if not self.audio_buffer:
                continue

            audio = np.array(self.audio_buffer, dtype=np.float32)
            self.audio_buffer.clear()

            # Skip silence
            rms = np.sqrt(np.mean(audio**2))
            if rms < SILENCE_THRESHOLD:
                continue

            try:
                result = mlx_whisper.transcribe(
                    audio,
                    path_or_hf_repo=self.model,
                    language="en",
                )
                text = result.get("text", "").strip()
                if text and len(text.split()) >= 3:
                    print(f"[speech] {text}")
                    self.text_queue.put(text)
            except Exception as e:
                print(f"[whisper] Error: {e}", file=sys.stderr)

    def stop(self):
        self.running = False
        if hasattr(self, "stream"):
            self.stream.stop()
            self.stream.close()


class IllustrationDisplay:
    """PyQt6 window that shows generated illustrations with progressive reveal."""

    def __init__(self):
        from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget
        from PyQt6.QtCore import Qt, pyqtSignal, QObject
        from PyQt6.QtGui import QPixmap, QImage

        self.app = QApplication.instance() or QApplication(sys.argv)

        self.window = QWidget()
        self.window.setWindowTitle("NarrateVision")
        self.window.setStyleSheet("background-color: #1a1a2e;")
        self.window.resize(1024, 768)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background-color: #1a1a2e;")
        layout.addWidget(self.image_label)

        self.status_label = QLabel("Listening... Start reading aloud.")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(
            "color: #e0e0e0; font-size: 16px; padding: 10px; "
            "background-color: #16213e; font-family: system-ui;"
        )
        layout.addWidget(self.status_label)

        self.window.setLayout(layout)

        # Store references for use in callbacks
        self._QPixmap = QPixmap
        self._QImage = QImage
        self._Qt = Qt

    def show(self):
        self.window.show()

    def update_image(self, image_bytes: bytes):
        """Update the displayed image from raw bytes."""
        try:
            img = Image.open(io.BytesIO(image_bytes))
            img = img.convert("RGB")
            data = img.tobytes()
            qimg = self._QImage(
                data, img.width, img.height,
                3 * img.width,
                self._QImage.Format.Format_RGB888,
            )
            pixmap = self._QPixmap.fromImage(qimg)

            # Scale to fit window while maintaining aspect ratio
            scaled = pixmap.scaled(
                self.image_label.size(),
                self._Qt.AspectRatioMode.KeepAspectRatio,
                self._Qt.TransformationMode.SmoothTransformation,
            )
            self.image_label.setPixmap(scaled)
        except Exception as e:
            print(f"[display] Error updating image: {e}", file=sys.stderr)

    def update_status(self, text: str):
        """Update the status bar text."""
        self.status_label.setText(text)

    def run(self):
        """Start the Qt event loop."""
        self.app.exec()


class NarrateVision:
    """Main orchestrator: wires together speech, scene extraction, and illustration."""

    def __init__(self):
        self.text_queue = queue.Queue()
        self.sentences = []
        self.last_prompt = None
        self.last_gen_time = 0
        self.generating = False

    def run(self):
        # Check ComfyUI is running
        if not is_comfyui_running():
            print(
                "\n[error] ComfyUI is not running."
                "\n        Start it first: cd /Volumes/X9Pro/Developer/ComfyUI && python3 main.py"
                "\n        Then run this script again.\n"
            )
            sys.exit(1)

        print("NarrateVision")
        print("=============")
        print("Read aloud or speak, and watch scenes illustrated in real-time.")
        print("Press Ctrl+C to stop.\n")

        # Start display
        self.display = IllustrationDisplay()
        self.display.show()

        # Start transcription in background thread
        self.transcriber = TranscriptionWorker(self.text_queue)
        transcribe_thread = threading.Thread(target=self.transcriber.start, daemon=True)
        transcribe_thread.start()

        # Start scene processing in background thread
        scene_thread = threading.Thread(target=self._scene_loop, daemon=True)
        scene_thread.start()

        # Handle Ctrl+C
        signal.signal(signal.SIGINT, lambda *_: self._shutdown())

        # Run Qt event loop (blocks)
        self.display.run()

    def _scene_loop(self):
        """Process transcript text and trigger image generation."""
        from PyQt6.QtCore import QMetaObject, Qt, Q_ARG

        while True:
            try:
                text = self.text_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            self.sentences.append(text)

            # Check cooldown
            elapsed = time.time() - self.last_gen_time
            if elapsed < SCENE_COOLDOWN:
                continue

            # Skip if already generating
            if self.generating:
                continue

            # Try to extract a scene
            prompt = extract_scene_from_accumulator(self.sentences, self.last_prompt)
            if not prompt:
                continue

            # Check we have enough words
            total_words = sum(len(s.split()) for s in self.sentences[-3:])
            if total_words < MIN_WORDS_FOR_SCENE:
                continue

            self.generating = True
            self.last_prompt = prompt
            self.last_gen_time = time.time()

            print(f"\n[scene] Generating: {prompt[:80]}...")

            # Update status on UI thread
            QMetaObject.invokeMethod(
                self.display.status_label,
                "setText",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, f"Illustrating: {prompt[:60]}..."),
            )

            try:
                def on_preview(img_bytes):
                    """Show progressive preview as image generates."""
                    QMetaObject.invokeMethod(
                        self.display.window,
                        "update",
                        Qt.ConnectionType.QueuedConnection,
                    )
                    # Update image on main thread
                    self.display.update_image(img_bytes)

                def on_progress(step, total):
                    status = f"Rendering step {step}/{total}..."
                    QMetaObject.invokeMethod(
                        self.display.status_label,
                        "setText",
                        Qt.ConnectionType.QueuedConnection,
                        Q_ARG(str, status),
                    )

                image_bytes = generate_with_progress(
                    prompt,
                    on_preview=on_preview,
                    on_progress=on_progress,
                )

                if image_bytes:
                    self.display.update_image(image_bytes)
                    QMetaObject.invokeMethod(
                        self.display.status_label,
                        "setText",
                        Qt.ConnectionType.QueuedConnection,
                        Q_ARG(str, "Listening... Keep reading."),
                    )
                    print("[scene] Done.")

            except Exception as e:
                print(f"[scene] Generation error: {e}", file=sys.stderr)

            self.generating = False

    def _shutdown(self):
        print("\n[exit] Shutting down...")
        self.transcriber.stop()
        self.display.app.quit()


if __name__ == "__main__":
    app = NarrateVision()
    app.run()

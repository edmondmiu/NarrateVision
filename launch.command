#!/bin/bash
# NarrateVision launcher - double-click to start everything

COMFYUI_DIR="/Volumes/X9Pro/Developer/ComfyUI"
NARRATE_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT=3456

echo "NarrateVision"
echo "============="
echo ""

# Check ComfyUI
if ! curl -s http://127.0.0.1:8188/system_stats > /dev/null 2>&1; then
    echo "Starting ComfyUI..."
    cd "$COMFYUI_DIR"
    python3 main.py --listen 127.0.0.1 --port 8188 --enable-cors-header "*" > /tmp/comfyui.log 2>&1 &
    COMFY_PID=$!

    echo "Waiting for ComfyUI to start..."
    for i in $(seq 1 60); do
        if curl -s http://127.0.0.1:8188/system_stats > /dev/null 2>&1; then
            echo "ComfyUI is running."
            break
        fi
        sleep 2
    done

    if ! curl -s http://127.0.0.1:8188/system_stats > /dev/null 2>&1; then
        echo "ERROR: ComfyUI failed to start after 2 minutes."
        exit 1
    fi
else
    echo "ComfyUI already running."
fi

# Serve the HTML
echo "Starting web server on port $PORT..."
cd "$NARRATE_DIR/static"
python3 -m http.server $PORT &
WEB_PID=$!

sleep 1

# Open browser
echo "Opening browser..."
open "http://localhost:$PORT"

echo ""
echo "Ready! Browser should be open at http://localhost:$PORT"
echo "Press Ctrl+C to stop everything."
echo ""

# Wait and clean up on exit
trap "kill $WEB_PID 2>/dev/null; kill $COMFY_PID 2>/dev/null; echo 'Stopped.'; exit 0" INT TERM
wait

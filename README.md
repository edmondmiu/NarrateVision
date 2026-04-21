# NarrateVision

Speak or read aloud and watch scenes illustrated in real-time. Runs entirely in the browser — no server, no install. Bring your own fal.ai API key.

## Try it

1. Open the site.
2. Sign up at [fal.ai](https://fal.ai) and grab your key from the [dashboard](https://fal.ai/dashboard/keys).
3. Paste it into **Settings**. The key is stored in your browser's localStorage and only ever sent to fal.ai.
4. Click **Start Listening** and read aloud. Illustrations appear every couple of seconds as the scene changes.

Each image costs roughly $0.002 on fal.ai and takes 1-2 seconds to generate.

## How it works

```
Browser mic (Web Speech API)
        ↓  transcript
  Scene extractor (keyword match)
        ↓  prompt
  fal.ai fast-lightning-sdxl
        ↓  image URL
  Browser display (fade-in)
```

1. Chrome captures speech via the Web Speech API. Transcription happens locally in the browser.
2. A small keyword-based scene extractor picks out characters, settings, actions, and atmosphere from the rolling transcript.
3. The extracted scene becomes a prompt sent to [fal.ai/fast-lightning-sdxl](https://fal.ai/models/fal-ai/fast-lightning-sdxl).
4. The returned image URL fades into view. Thumbnails of previous scenes appear in a strip below.

## Requirements

- Chrome or Edge (Web Speech API is not available in Safari or Firefox).
- A fal.ai account with credits.

That's it. No Python, no GPU, no ComfyUI.

## Local development

```bash
git clone https://github.com/edmondmiu/NarrateVision.git
cd NarrateVision
# Open public/index.html with any static server, e.g.
npx serve public
```

## Deploy

Deployed via Firebase Hosting on the `edmondmiu@gmail.com` account. To deploy your own copy:

```bash
npm install -g firebase-tools
firebase login
firebase init hosting   # pick an existing project or create one, use `public` as the directory
firebase deploy
```

## Project layout

| File | Purpose |
|---|---|
| `public/index.html` | The entire app: UI, mic capture, scene extraction, fal.ai calls |
| `firebase.json` | Firebase Hosting config |

## History

The original version ran fully locally: Python server + ComfyUI + SD 1.5 + Hyper-SD LoRA on an M1 Pro. That version is preserved in git history before commit `<rewrite>`. This rewrite traded local-only for shareable-online — same UX, hosted image generation.

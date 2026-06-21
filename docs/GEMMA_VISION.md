---
title: Gemma Vision
---

# Gemma Vision Integration

STASIS uses Gemma on the Windows laptop/server to inspect USB webcam frames captured by the Raspberry Pi. The rover does not run Gemma; the Raspberry Pi 2B captures the webcam, streams frames to Windows, receives `vision_result`, decides the action, and sends `vision_decision` back to the dashboard/server.

Gemma is now one supported local provider, not the only vision option. For Gemini API, OpenAI, Anthropic, Qwen DashScope, Kimi, Zhipu, Ollama, or LM Studio, use `docs/VISION_PROVIDERS.md`.

## Default Model

The server defaults to:

```text
google/gemma-4-E2B-it
```

This is a multimodal Gemma instruct model that supports image + text input through Hugging Face Transformers. The server uses the documented `any-to-any` pipeline and sends a chat-style message containing:

```text
1. The latest Raspberry Pi webcam frame as a PIL image.
2. A strict JSON instruction prompt.
```

The expected model response is:

```json
{"detected": true, "category": "human", "message": "person visible beside the patrol marker"}
```

or:

```json
{"detected": false, "category": "", "message": ""}
```

The server calls the pipeline with `return_full_text=False` and deterministic generation settings so the parser sees only Gemma's new answer, not the original prompt.

## Hugging Face Access

Gemma 4 model weights are hosted on Hugging Face. If your environment needs authentication for downloads or you hit rate limits, create a Hugging Face access token.

Set the token before starting the server.

PowerShell:

```powershell
$env:HF_TOKEN = "hf_your_token_here"
```

Bash:

```bash
export HF_TOKEN="hf_your_token_here"
```

You can also run `huggingface-cli login` on the server machine.

## Install

Install the normal server requirements. They include the Transformers version needed for Gemma any-to-any inference.

Windows PowerShell:

```powershell
cd server
py -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements-windows.txt
```

Linux:

```bash
cd server
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If you are using only API providers, Ollama, or LM Studio, install `requirements-api.txt` instead. That lighter install does not require Torch.

## Configuration

For local Gemma, copy `server/vision_config.example.json` to `server/vision_config.json`, enable `local_gemma`, and put it in `provider_order`. The legacy environment variables below still work for Gemma tuning when needed:

```text
STASIS_VISION_ENABLED=true
STASIS_VISION_REQUIRED=false
STASIS_VISION_MODEL=google/gemma-4-E2B-it
STASIS_VISION_PIPELINE_TASK=any-to-any
STASIS_VISION_DEVICE=auto
STASIS_VISION_DEVICE_MAP=none
STASIS_VISION_TORCH_DTYPE=auto
STASIS_VISION_MAX_NEW_TOKENS=160
STASIS_ANALYSIS_INTERVAL_SECONDS=2
STASIS_CAMERA_SOURCE=rover
STASIS_CAMERA_INDEX=0
STASIS_CAMERA_WIDTH=640
STASIS_CAMERA_HEIGHT=480
STASIS_CAMERA_FPS=15
STASIS_CAMERA_BACKEND=dshow
```

Recommended Windows CUDA settings:

```powershell
$env:STASIS_VISION_DEVICE = "cuda"
$env:STASIS_VISION_DEVICE_MAP = "none"
$env:STASIS_VISION_TORCH_DTYPE = "bfloat16"
$env:STASIS_VISION_REQUIRED = "true"
python security_rover_server_windows.py
```

CPU fallback:

```powershell
$env:STASIS_VISION_DEVICE = "cpu"
$env:STASIS_VISION_DEVICE_MAP = "none"
$env:STASIS_VISION_TORCH_DTYPE = "float32"
python security_rover_server_windows.py
```

CPU inference can be slow. If you only want to test rover control and the dashboard, disable vision:

```powershell
$env:STASIS_VISION_ENABLED = "false"
python security_rover_server_windows.py
```

## Prompt Contract

The server prompt asks Gemma to return only one JSON object:

```json
{"detected": boolean, "category": "human|animal|track|fire|marker", "message": string}
```

The parser accepts plain JSON or the first valid JSON object embedded in extra model text. If `detected` is false, the server clears `message` before broadcasting. If the category is missing or outside the STASIS categories, the alert is suppressed. If the response cannot be parsed, the error is logged and no alert is emitted for that frame.

The default categories for the forest-monitoring demo are:

```text
human   -> humans, intruders, people in the test area
animal  -> animals or wildlife stand-ins
track   -> footprints, trails, soil changes, disturbed ground, track marks
fire    -> flame, smoke, fire-like hazards
marker  -> custom navigation markers such as green strips
```

The demo is indoors, but the prompt treats the scene as a staged forest floor. It intentionally avoids alerting on ordinary doors or windows unless they matter to the demo setup.

To customize the prompt:

PowerShell:

```powershell
$env:STASIS_ANALYSIS_PROMPT = "Analyze this STASIS forest-monitoring rover frame for humans, animals, tracks, fire, or red navigation strips. Return only JSON with detected and message."
```

Keep the same JSON schema so the dashboard and category filter continue to work.

## Troubleshooting

If model loading fails with an authorization error:

```text
1. Set HF_TOKEN or run huggingface-cli login.
2. Restart the server.
```

If model loading fails because of Transformers support:

```bash
pip install --upgrade "transformers>=4.53.0" torch torchvision accelerate sentencepiece protobuf
```

If CUDA runs out of memory:

```text
1. Lower STASIS_CAMERA_WIDTH and STASIS_CAMERA_HEIGHT.
2. Increase STASIS_ANALYSIS_INTERVAL_SECONDS.
3. Try STASIS_VISION_TORCH_DTYPE=bfloat16.
4. Disable vision while testing rover control.
```

If the wrong webcam opens on the Raspberry Pi, change `camera.index` in `rover/rpi2b/config.json`, then restart the Pi rover client. If you intentionally test with a laptop webcam, set `STASIS_CAMERA_SOURCE=local` on Windows and then use `STASIS_CAMERA_INDEX`.

If alerts are noisy, adjust `STASIS_ANALYSIS_PROMPT` to describe only the objects or events that matter for your test space.

## References

- Hugging Face model page: https://huggingface.co/google/gemma-4-E2B-it
- Google Gemma documentation: https://ai.google.dev/gemma

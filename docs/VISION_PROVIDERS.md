---
title: Vision Providers
---

# Multimodal Vision Providers

STASIS can use a cloud multimodal API, a local Ollama model, LM Studio, or the original local Gemma path. The Raspberry Pi still captures the USB webcam and sends frames to the Windows laptop. The Windows laptop sends each selected frame to the configured vision provider, receives JSON, and sends the result back to the Raspberry Pi so the rover can decide what to do.

Use this when local Gemma is too heavy for your laptop, when Torch is not installing cleanly, or when you want to test several multimodal models without changing Python code.

## Recommended Demo Setup

For the smoothest local demo, start with the Moondream two-stage Ollama setup. Keep cloud APIs as backup if the competition network allows them.

```text
Raspberry Pi webcam frame
  -> Windows server
  -> Moondream checks the image
  -> tiny text model converts the notes into STASIS JSON
  -> if local models fail, try Gemini / OpenAI / Qwen / Zhipu / Anthropic / Kimi API
  -> Raspberry Pi receives vision_result
  -> Raspberry Pi decides stop, alert, marker memory, or continue
```

## Setup

On Windows:

```powershell
cd server
copy vision_config.example.json vision_config.json
py -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements-api.txt
```

Open `server/vision_config.json` and turn on the provider you want:

```json
"gemini": {
  "type": "gemini",
  "enabled": true,
  "api_key_env": "GEMINI_API_KEY",
  "base_url": "https://generativelanguage.googleapis.com/v1beta",
  "model": "gemini-2.5-flash-lite"
}
```

Set the matching API key in the same PowerShell window before starting the server:

```powershell
$env:GEMINI_API_KEY = "your_key_here"
python security_rover_server_windows.py
```

Do not put real API keys directly into GitHub. The real `server/vision_config.json` file is ignored by Git.

## Provider Order

The server tries providers in this order:

```json
"provider_order": [
  "gemini",
  "openai",
  "qwen_dashscope",
  "zhipu",
  "ollama",
  "lmstudio"
]
```

Only enabled providers are used. If a provider fails, STASIS logs the error and tries the next enabled provider.

## Recommended Local Setup: Moondream + Tiny Text Model

Gemma 4 E2B is accurate but can be too slow on a laptop during a live robot demo. The recommended local setup splits the work into two smaller jobs:

```text
Moondream       -> looks at the camera frame
qwen2.5:0.5b    -> converts Moondream notes into clean STASIS JSON
```

Install the models:

```powershell
ollama pull moondream
ollama pull qwen2.5:0.5b
```

Enable this provider in `server/vision_config.json`:

```json
"moondream_stasis": {
  "type": "ollama_moondream_pipeline",
  "enabled": true,
  "base_url": "http://127.0.0.1:11434",
  "vision_model": "moondream",
  "text_model": "qwen2.5:0.5b",
  "jpeg_quality": 60,
  "vision_timeout_seconds": 20,
  "formatter_timeout_seconds": 15,
  "vision_max_tokens": 96,
  "formatter_max_tokens": 120,
  "use_text_formatter": true
}
```

Put it first:

```json
"provider_order": [
  "moondream_stasis",
  "gemini",
  "zhipu",
  "qwen_dashscope",
  "ollama",
  "lmstudio",
  "local_gemma"
]
```

Use this for the competition demo because it is faster and more focused than asking one large model to do every vision and explanation task.

## Supported Cloud Providers

The example config includes:

```text
gemini          Google Gemini API
openai          OpenAI vision-capable chat models
anthropic       Claude vision models
qwen_dashscope  Alibaba Cloud DashScope Qwen-VL models
kimi            Moonshot Kimi vision models, if available for your account
zhipu           Zhipu GLM vision models
```

Most of these providers use either the OpenAI-compatible chat format or their own official multimodal format. You can change `base_url`, `model`, and `api_key_env` in `vision_config.json` without touching code.

## Cheapest Or Free Options To Try

Prices and free quotas change, so check the official pricing page before the final demo. For your project, try them in this order:

1. Moondream + `qwen2.5:0.5b` through Ollama, free local setup with no API key.
2. Gemini API free tier or Flash-Lite style models, if your quota works.
3. Z.AI / Zhipu `glm-4.6v-flash`, which is a free vision model in their official pricing docs.
4. Alibaba DashScope `qwen3-vl-8b-instruct`, which is a low-cost Chinese multimodal model.
5. OpenAI small vision models, usually reliable and cheap but not normally free.
6. Anthropic Haiku vision models, good quality but usually paid.

If your Gemini quota is exhausted, keep Gemini in the config but put another provider before it in `provider_order`.

Official pricing pages to check before the demo:

```text
Google Gemini API: https://ai.google.dev/gemini-api/docs/pricing
Z.AI / Zhipu:      https://docs.z.ai/guides/overview/pricing
Alibaba Qwen:      https://www.alibabacloud.com/help/en/model-studio/model-pricing
OpenAI:            https://platform.openai.com/docs/pricing
Anthropic:         https://platform.claude.com/docs/en/about-claude/pricing
```

## Single-Model Ollama Fallback

If you want one Ollama model instead of the Moondream pipeline, install Ollama on the Windows laptop, then pull a vision-capable model:

```powershell
ollama pull llava:7b
```

Enable Ollama in `vision_config.json`:

```json
"ollama": {
  "type": "ollama",
  "enabled": true,
  "base_url": "http://127.0.0.1:11434",
  "model": "llava:7b"
}
```

Then put `ollama` near the end of `provider_order`. This makes it a backup when cloud APIs fail.

## LM Studio Fallback

In LM Studio:

1. Download a vision-capable model.
2. Start the local server.
3. Keep the server URL as `http://127.0.0.1:1234/v1`.
4. Set the exact model name in `vision_config.json`.

Example:

```json
"lmstudio": {
  "type": "openai_compatible",
  "enabled": true,
  "base_url": "http://127.0.0.1:1234/v1",
  "model": "your-loaded-vision-model",
  "json_mode": false
}
```

Some local models do not support strict JSON mode, so LM Studio defaults to `"json_mode": false`.

## Troubleshooting

If an OpenAI-compatible provider says `response_format` is not supported, set this for that provider:

```json
"json_mode": false
```

The STASIS prompt still asks for JSON, and the server parser will extract the first JSON object from normal text.

## Local Gemma

The original local Gemma path is still available, but it needs the full heavy install:

```powershell
pip install -r requirements-windows.txt
```

Then enable:

```json
"local_gemma": {
  "type": "local_gemma",
  "enabled": true,
  "model": "google/gemma-4-E2B-it",
  "pipeline_task": "any-to-any"
}
```

Use this only if your laptop has enough RAM and the model starts reliably. API mode does not need Torch.

## What The Model Must Return

Every provider is asked to return this JSON:

```json
{"detected": true, "category": "human", "message": "person visible near the Green Strip"}
```

Allowed categories:

```text
human
animal
track
fire
marker
```

The server filters anything outside those categories so the project does not drift away from the STASIS mission.

# Multimodal Vision Providers

STASIS can use a cloud multimodal API, a local Ollama model, LM Studio, or the original local Gemma path. The Raspberry Pi still captures the USB webcam and sends frames to the Windows laptop. The Windows laptop sends each selected frame to the configured vision provider, receives JSON, and sends the result back to the Raspberry Pi so the rover can decide what to do.

Use this when local Gemma is too heavy for your laptop, when Torch is not installing cleanly, or when you want to test several multimodal models without changing Python code.

## Recommended Demo Setup

For the smoothest demo, start with an API provider first, then keep Ollama or LM Studio as the local fallback.

```text
Raspberry Pi webcam frame
  -> Windows server
  -> Gemini / OpenAI / Qwen / Zhipu / Anthropic / Kimi API
  -> if API fails, try Ollama or LM Studio
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

1. Gemini API free tier or Flash-Lite style models, if your quota works.
2. Z.AI / Zhipu `glm-4.6v-flash`, which is a free vision model in their official pricing docs.
3. Alibaba DashScope `qwen3-vl-8b-instruct`, which is a low-cost Chinese multimodal model.
4. OpenAI small vision models, usually reliable and cheap but not normally free.
5. Anthropic Haiku vision models, good quality but usually paid.
6. Ollama or LM Studio, free after setup because it runs locally, but slower and limited by laptop RAM.

If your Gemini quota is exhausted, keep Gemini in the config but put another provider before it in `provider_order`.

Official pricing pages to check before the demo:

```text
Google Gemini API: https://ai.google.dev/gemini-api/docs/pricing
Z.AI / Zhipu:      https://docs.z.ai/guides/overview/pricing
Alibaba Qwen:      https://www.alibabacloud.com/help/en/model-studio/model-pricing
OpenAI:            https://platform.openai.com/docs/pricing
Anthropic:         https://platform.claude.com/docs/en/about-claude/pricing
```

## Ollama Fallback

Install Ollama on the Windows laptop, then pull a vision-capable model:

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
{"detected": true, "category": "human", "message": "person visible near the red strip"}
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

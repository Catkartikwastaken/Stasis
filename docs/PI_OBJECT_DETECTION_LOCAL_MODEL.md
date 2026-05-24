# Pi Object Detection + Local Model Alerts

This mode adds a more practical detection path based on the Core Electronics OpenCV/COCO Raspberry Pi pattern.

Instead of asking a heavy vision model to inspect every frame, the Raspberry Pi first runs a lightweight COCO object detector. When the Pi sees configured objects such as `person`, `dog`, `cat`, `bird`, `cow`, or `bear`, it sends structured detection notes to the Windows server. The server then asks a local text model, such as Qwen through Ollama or LM Studio, to convert those notes into the existing STASIS alert JSON.

## Flow

```text
Pi webcam
  -> OpenCV COCO detection on Raspberry Pi
  -> object_detection WebSocket message
  -> Windows server asks local Qwen/Ollama or Qwen/LM Studio
  -> server sends vision_result to Pi
  -> Pi stops/alerts/remembers marker using the existing rover logic
  -> dashboard receives the normal alert card
```

## New Entry Points

Run this server on the Windows laptop:

```powershell
cd server
python security_rover_server_object_detection.py
```

Run this rover client on the Raspberry Pi:

```bash
cd rover/rpi2b
python rover_client_object_detection.py --config config.json
```

The original scripts still exist and can be used if you want the old multimodal-frame pipeline.

## Local Model Options

### Ollama

On the Windows laptop, start Ollama and pull a small Qwen model:

```powershell
ollama pull qwen2.5:0.5b
$env:STASIS_OBJECT_REVIEW_PROVIDER = "ollama"
$env:STASIS_OLLAMA_URL = "http://127.0.0.1:11434"
$env:STASIS_OLLAMA_TEXT_MODEL = "qwen2.5:0.5b"
python security_rover_server_object_detection.py
```

### LM Studio

In LM Studio, start the local OpenAI-compatible server, then run:

```powershell
$env:STASIS_OBJECT_REVIEW_PROVIDER = "lmstudio"
$env:STASIS_LMSTUDIO_URL = "http://127.0.0.1:1234/v1"
$env:STASIS_LMSTUDIO_TEXT_MODEL = "your-loaded-qwen-model-name"
python security_rover_server_object_detection.py
```

### No Local Model

For the most reliable emergency demo, use the deterministic fallback. It does not call any model; it maps COCO `person` to `human` and common animals to `animal`.

```powershell
$env:STASIS_OBJECT_REVIEW_PROVIDER = "fallback"
python security_rover_server_object_detection.py
```

## Raspberry Pi Model Files

Create this folder on the Pi:

```bash
mkdir -p rover/rpi2b/models
```

Place these files in it:

```text
rover/rpi2b/models/coco.names
rover/rpi2b/models/ssd_mobilenet_v3_large_coco_2020_01_14.pbtxt
rover/rpi2b/models/frozen_inference_graph.pb
```

These are the same kind of COCO MobileNet SSD files used in many Raspberry Pi OpenCV object-detection guides. Keep them out of git if they are large.

## Pi Config

Start from:

```bash
cp object_detection_config.example.json config.json
```

Edit `server_host` to the Windows laptop IP. The important section is:

```json
"object_detection": {
  "enabled": true,
  "confidence_threshold": 55,
  "target_classes": ["person", "bird", "cat", "dog", "horse", "sheep", "cow", "bear"],
  "alert_cooldown_seconds": 8.0
}
```

Raise `confidence_threshold` if alerts are noisy. Lower it if the detector misses too much. The value is a percentage, so `55` means 55%.

## Why This Helps

The old flow asked the model to understand raw frames directly. This flow gives the local model clean facts first:

```text
label=person, confidence=81%, box={...}
```

That is much easier for a small local Qwen model to reason over, and it also gives you a fallback path if the local model fails.

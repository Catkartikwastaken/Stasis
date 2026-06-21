---
title: Windows YOLO ONNX Detection
---

# Windows YOLO ONNX Detection

This is the recommended STASIS demo setup when the Raspberry Pi 2B cannot run YOLO/Torch.

## What Runs Where

```text
Raspberry Pi 2B
  - streams USB webcam frames
  - receives rover commands
  - controls motors and sensors

Windows laptop
  - hosts dashboard
  - receives Pi camera stream
  - runs YOLO ONNX object detection
  - creates human, animal, and object alerts
  - sends vision_result commands back to the Pi
```

This avoids installing `torch` or `ultralytics` on the Pi.

## Windows Setup

From the repo root on Windows:

```powershell
cd server
python -m pip install -r requirements-object-detection.txt
```

Put the ONNX model here:

```text
server/models/yolo11n.onnx
```

If you only have `yolo11n.pt`, export it on Windows, not on the Pi:

```powershell
python -m pip install ultralytics
yolo export model=yolo11n.pt format=onnx imgsz=640 simplify=True
mkdir models
move yolo11n.onnx models\yolo11n.onnx
```

Start the Windows server:

```powershell
$env:STASIS_CAMERA_SOURCE = "rover"
$env:STASIS_OBJECT_REVIEW_PROVIDER = "fallback"
$env:STASIS_YOLO_ONNX_MODEL = "models/yolo11n.onnx"
python security_rover_server_object_detection.py
```

## False-Positive Filtering

The YOLO model is not retrained. STASIS makes it stricter with server-side post-processing in `server/detection_filtering.py`.

Tune the central config in `server/detection_filter_config.json`, or point `STASIS_DETECTION_FILTER_CONFIG` at another JSON file. The default gate is intentionally conservative:

```text
Human confidence: 0.70
Object/wildlife confidence: 0.75
Persistence: 5 consecutive stable frames
Minimum box area: 2% of the frame
Edge exclusion: top/bottom 10%, left/right 5%
Duplicate alert cooldown: 10 seconds
```

Dashboard detections appear first as Detection Candidate. Only Confirmed Detection entries can trigger alerts, screenshots, notifications, rover commands, or saved alert records.

Open:

```text
http://192.168.29.69:5000
```

Use your current Windows IP if it changes.

## Raspberry Pi Setup

The Pi does not need YOLO, Torch, Ultralytics, or ONNX Runtime.

Run the normal rover client:

```bash
cd ~/Documents/Stasis/rover/rpi2b
source .venv/bin/activate
python rover_client.py --config config.json
```

Make sure `config.json` points to the Windows laptop:

```json
"server_host": "192.168.29.69"
```

## Expected Result

When the Pi webcam sees a person, animal, or object:

```text
Windows terminal: Windows YOLO detections: ...
Dashboard: alert card appears
Map: dot appears
Track: shows forward/left/right guidance in centimeters
Pi: receives vision_result and can stop for human/fire
```

## If No Alert Appears

Check these first:

```powershell
dir server\models
python -c "import onnxruntime; print('onnxruntime ok')"
```

The server terminal must say:

```text
Windows YOLO ONNX detector loaded from ...
```

If it says the model is missing, put `yolo11n.onnx` in `server/models/`.

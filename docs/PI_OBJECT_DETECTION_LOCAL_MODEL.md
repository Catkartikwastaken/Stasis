---
title: Pi Object Detection Local Model
---

# Pi Object Detection Local Model

STASIS can run a Pi-only detector when the demo must work without laptop-side AI.

For best Pi 2B behavior, use the combined detector:

```text
custom YOLO model -> your demo objects
OpenCV COCO model -> person + cell phone
Green Strip detector -> optional color marker
```

This lets your custom model stay focused on your demo objects while the older COCO detector covers humans and mobile phones.

## Recommended Config

Edit:

```bash
nano ~/Documents/Stasis/rover/rpi2b/config.json
```

Use these important values inside `object_detection`:

```json
{
  "backend": "combined",
  "yolo_model_path": "models/best.pt",
  "target_classes": [],
  "common_detection_enabled": true,
  "common_target_classes": ["person", "cell phone"],
  "class_names_path": "models/coco.names",
  "config_path": "models/ssd_mobilenet_v3_large_coco_2020_01_14.pbtxt",
  "weights_path": "models/frozen_inference_graph.pb",
  "confidence_threshold": 55,
  "nms_threshold": 20,
  "input_size": 320,
  "overlay_enabled": true,
  "stream_interval_seconds": 0.12,
  "stream_jpeg_quality": 50,
  "upload_interval_seconds": 1.5
}
```

If your custom model is an exported NCNN folder, set:

```json
"yolo_model_path": "models/best_ncnn_model"
```

With an NCNN folder, the Pi client loads `model.ncnn.param` and `model.ncnn.bin` directly. It does not need Ultralytics for the custom model.

## Files Needed On The Pi

Put custom model here:

```text
~/Documents/Stasis/rover/rpi2b/models/best.pt
```

Or:

```text
~/Documents/Stasis/rover/rpi2b/models/best_ncnn_model/
```

Keep these COCO files too:

```text
~/Documents/Stasis/rover/rpi2b/models/coco.names
~/Documents/Stasis/rover/rpi2b/models/ssd_mobilenet_v3_large_coco_2020_01_14.pbtxt
~/Documents/Stasis/rover/rpi2b/models/frozen_inference_graph.pb
```

## Install

```bash
cd ~/Documents/Stasis/rover/rpi2b
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-object-detection.txt
```

Only install Ultralytics if you are trying to run a `.pt` model directly on the Pi:

```bash
python -m pip install ultralytics
```

If this fails because of `torch`, use an exported model format that works on your Pi environment, or run only the OpenCV COCO detector with:

```json
"backend": "opencv"
```

## Run

```bash
cd ~/Documents/Stasis/rover/rpi2b
source .venv/bin/activate
python rover_client_object_detection.py --config config.json
```

Good startup logs should include:

```text
Pi-side YOLO object detector loaded
Pi-side COCO object detector loaded
Combined detector ready
WebSocket handshake successful
```

## What It Detects

Your custom model detects the classes it was trained with. For the current exported model, examples include:

```text
cardboard
debit card
green strip
paper
plastic covers
plastic water bottle
steel water bottle
torch
wallet
wood
```

The common model detects:

```text
person
cell phone
```

All detections are drawn on the livestream when `overlay_enabled` is `true`.

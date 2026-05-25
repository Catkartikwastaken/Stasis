---
title: Pi Object Detection Local Model
---

# Legacy Pi Object Detection

This document is kept for reference only.

The current recommended STASIS demo does **not** run YOLO or object detection on the Raspberry Pi 2B. The Pi 2B has trouble installing the Torch dependency required by Ultralytics/YOLO, especially on Python 3.13 and ARMv7.

Use this instead:

```text
Pi webcam stream -> Windows laptop -> YOLO ONNX detection -> dashboard + rover command
```

See:

```text
docs/WINDOWS_YOLO_ONNX_DETECTION.md
```

## Why Pi Detection Was Replaced

The Pi-side YOLO path failed with:

```text
ultralytics depends on torch
no matching distributions available for your environment: torch
```

That means the Pi can stream frames, but it cannot run the YOLO detector reliably in this setup.

## What To Run On The Pi Now

Run the normal rover client:

```bash
cd ~/Documents/Stasis/rover/rpi2b
source .venv/bin/activate
python rover_client.py --config config.json
```

The Pi only needs:

```text
websocket-client
smbus2
RPi.GPIO
pyserial
opencv-python
```

It does not need:

```text
torch
ultralytics
onnxruntime
```

## If You Still Want To Experiment

The file `rover_client_object_detection.py` still exists as an experimental path. It can use older OpenCV DNN model files or YOLO if a compatible environment is available.

For the competition demo, use Windows YOLO ONNX instead.

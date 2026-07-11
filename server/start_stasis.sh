#!/usr/bin/env bash
# STASIS Server Launcher — GPU-accelerated mode (Ultralytics + CUDA)
# Usage: ./start_stasis.sh
set -e
cd "$(dirname "$0")"

export STASIS_CAMERA_SOURCE=local
export STASIS_CAMERA_INDEX=0
export STASIS_CAMERA_WIDTH=640
export STASIS_CAMERA_HEIGHT=480
export STASIS_CAMERA_FPS=30
export STASIS_CAMERA_BACKEND=dshow
export STASIS_VISION_ENABLED=false
export STASIS_STREAM_FPS=20
export STASIS_STREAM_JPEG_QUALITY=50
export STASIS_STREAM_FRAME_SKIP=1

# === GPU-Accelerated Detection (Ultralytics + CUDA) ===
export STASIS_DETECTOR_BACKEND=custom
export STASIS_WINDOWS_DETECTOR_RUNTIME=ultralytics
export STASIS_ULTRALYTICS_DEVICE=cuda:0
export STASIS_ULTRALYTICS_MODEL=yolo11n.pt
export STASIS_ULTRALYTICS_TARGET_CLASSES=person
export STASIS_ULTRALYTICS_IMGSZ=640
export STASIS_YOLO_CONFIDENCE=0.35
export STASIS_YOLO_NMS_THRESHOLD=0.45
export STASIS_YOLO_MAX_DETECTIONS=12
export STASIS_DETECTION_AUTHORITY=windows

echo "Starting STASIS Server with GPU-accelerated detection (GTX 1060)..."
echo "Dashboard: http://localhost:5000"
.venv/Scripts/python security_rover_server_object_detection.py

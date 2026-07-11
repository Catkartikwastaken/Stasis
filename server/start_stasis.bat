@echo off
cd /d C:\Users\Car\Stasis\server
set STASIS_CAMERA_SOURCE=rover
set STASIS_DETECTOR_BACKEND=custom
set STASIS_WINDOWS_DETECTOR_RUNTIME=ultralytics
set STASIS_ULTRALYTICS_DEVICE=cuda:0
set STASIS_ULTRALYTICS_CONFIDENCE=0.25
set STASIS_ULTRALYTICS_TARGET_CLASSES=person,animal
set STASIS_YOLOE_MODEL_PATH=yoloe-26s-seg.pt
set STASIS_YOLO_DRAW_OVERLAY=true
.venv\Scripts\python.exe security_rover_server_windows.py

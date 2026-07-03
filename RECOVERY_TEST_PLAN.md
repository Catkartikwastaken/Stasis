# STASIS Recovery & Test Plan

This document outlines the recovery and testing plan to ensure the STASIS rover project maintains a known working state.

## 1. Current Stable Architecture
* Raspberry Pi 2B handles camera streaming, motor control, and sensor readings.
* Laptop/base station handles dashboard.
* AI is currently disabled.
* `DETECTOR_BACKEND = "none"`
* `VISION_ENABLED = False`

## 2. How to Start the Server
* **Command to run:**
  ```powershell
  cd server
  python security_rover_server.py
  ```
* **Expected URL:** `http://127.0.0.1:5000`
* **Expected successful output:** Standard Flask/eventlet output indicating the server is running on `http://127.0.0.1:5000` with no critical errors or missing module tracebacks.

## 3. Manual Test Checklist
* [ ] Dashboard loads
* [ ] Stream panel appears
* [ ] Rover controls visible
* [ ] Sensor panel visible
* [ ] No AI imports required
* [ ] No repeated server errors

## 4. Things Not Allowed During Baseline Recovery
* No YOLOE
* No torch
* No cv2 requirement at startup
* No old UI restore
* No full refactor
* No deleting model files

## 5. Future Milestone Order
1. Baseline dashboard
2. Stream
3. Controls
4. Sensors
5. Logging
6. Detector backend none/custom/yoloe
7. False-positive filtering
8. YOLOE laptop-only experiment

## 6. Rollback Instructions
* Use the latest working commit
* Use the baseline tag if present
* Never force-push main

## Branch Safety Rules
- Do not work directly on main.
- Use separate branches for stream, controls, sensors, and detection.
- Merge only one branch at a time after testing.
- If a branch breaks the app, abandon the branch instead of fixing main.

## Known Working Baseline
- Record the commit hash of the current working dashboard baseline.
- Record the tag name if created: baseline-working-dashboard

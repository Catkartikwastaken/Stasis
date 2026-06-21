# STASIS Pi ↔ Laptop Integration (Stable Path)

This mode runs object detection on the **Windows laptop** while the **Pi only streams camera + telemetry**.

## 1) Windows laptop (server + detector)

From PowerShell:

```powershell
cd C:\Users\Car\Documents\Stasis\server
python -m pip install -r requirements-object-detection.txt

$env:STASIS_DETECTION_AUTHORITY="windows"
$env:STASIS_WINDOWS_DETECTOR_RUNTIME="ultralytics"
$env:STASIS_ULTRALYTICS_MODEL="yoloe-26s-seg.pt"
$env:STASIS_ULTRALYTICS_DEVICE="cuda:0"
$env:STASIS_REQUIRE_CUDA="false"
$env:STASIS_OBJECT_ANALYSIS_INTERVAL_SECONDS="0.2"

python security_rover_server_object_detection.py
```

Notes:
- If CUDA is unavailable and `STASIS_REQUIRE_CUDA=false`, server falls back to CPU.
- Dashboard URL: `http://127.0.0.1:5000`

## 2) Raspberry Pi (stream camera + rover control)

Use the profile `rover/rpi2b/profiles/laptop_detection_pi_stream.json`.

- This profile is stream-only (no Pi-side detector block).
- Set `server_host` in the profile to your laptop IP, or override via env:
  `export STASIS_SERVER_HOST=<LAPTOP_IP>`

Then run:

```bash
cd ~/Documents/Stasis/rover/rpi2b
source .venv/bin/activate
python rover_client.py --config profiles/laptop_detection_pi_stream.json
```

## 3) Validation checklist

- Pi logs show successful WebSocket handshake/registration.
- Laptop logs show: `Windows-side detection active with 1 detector(s).`
- Laptop logs show repeated detection debug entries after Pi frames arrive.
- Dashboard (`/`) shows live camera feed and detection overlays/debug rows.

## 4) Troubleshooting

- If camera feed is blank: verify Pi `server_host`, websocket path `/ws/rover`, and webcam index on Pi.
- If detections are missing: set `STASIS_ULTRALYTICS_MODEL="yolo11n.pt"` to sanity-check baseline detection.
- If too slow: lower `STASIS_ULTRALYTICS_IMGSZ` (for example `512`).

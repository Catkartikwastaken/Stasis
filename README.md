# STASIS Indoor Security Rover

This repository contains the current working prototype for the indoor security rover system.

## What Is Included

```text
firmware/esp32cam/esp32_cam_mjpeg_stream/esp32_cam_mjpeg_stream.ino
firmware/esp32s3/esp32s3_rover_ws.ino
server/security_rover_server.py
server/security_rover_server_windows.py
server/requirements.txt
server/requirements-windows.txt
server/templates/index.html
dashboard/rover_dashboard.html
dashboard/rover_dashboard_windows.html
docs/README_ROVER_SYSTEM.md
```

## Connection Map

```text
ESP32-CAM camera:      http://<ESP32_CAM_IP>/stream
Laptop server:         http://<SERVER_IP>:5000
Rover WebSocket:       ws://<SERVER_IP>:5000/ws/rover
Rover ID:              esp32s3_rover
Dashboard goal event:  set_goal
Alert event:           new_alert
Position event:        rover_position
```

## Important

The Wi-Fi SSID, Wi-Fi password, laptop IP, and camera IP are placeholders in this public repository. Replace them locally before flashing or running.

Read the full setup guide here:

```text
docs/README_ROVER_SYSTEM.md
```

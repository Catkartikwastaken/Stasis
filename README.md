# STASIS Indoor Security Rover

This repository contains the current working prototype for the indoor security rover system.

## What Is Included

```text
firmware/esp32cam/esp32_cam_mjpeg_stream/esp32_cam_mjpeg_stream.ino
firmware/esp32s3/esp32s3_rover_ws/esp32s3_rover_ws.ino
server/security_rover_server.py
server/security_rover_server_windows.py
server/requirements.txt
server/requirements-windows.txt
server/templates/index.html
dashboard/rover_dashboard.html
dashboard/rover_dashboard_windows.html
docs/README_ROVER_SYSTEM.md
```

## Network Connections

```text
ESP32-CAM camera:      http://<ESP32_CAM_IP>/stream
Laptop server:         http://<SERVER_IP>:5000
Rover WebSocket:       ws://<SERVER_IP>:5000/ws/rover
Rover ID:              esp32s3_rover
Dashboard goal event:  set_goal
Alert event:           new_alert
Position event:        rover_position
```

The ESP32-CAM and ESP32-S3 rover do not connect directly to each other with wires. They both join the same 2.4 GHz Wi-Fi network and communicate through the laptop server.

## Hardware Connections

ESP32-CAM AI-Thinker:

```text
5V       -> stable 5V supply
GND      -> supply ground
U0R/RX   -> USB-serial TX while uploading
U0T/TX   -> USB-serial RX while uploading
GPIO 0   -> GND only while uploading, then disconnect and reset
```

ESP32-S3 rover to L9110S motor driver:

```text
GPIO 26  -> A-IA
GPIO 27  -> A-IB
GPIO 14  -> B-IA
GPIO 12  -> B-IB
GND      -> L9110S GND and motor battery negative
VM/VCC   -> motor battery positive, matched to your motors/driver board
Motor A  -> left motor terminals
Motor B  -> right motor terminals
```

ESP32-S3 rover to MPU6050:

```text
GPIO 21  -> SDA
GPIO 22  -> SCL
3V3      -> VCC
GND      -> GND
```

ESP32-S3 rover to buzzer:

```text
GPIO 33  -> buzzer positive/input
GND      -> buzzer negative
```

Use a common ground between the ESP32-S3, motor driver, and motor battery. If a motor spins backward, swap that motor's two output wires or invert that motor in code.

## Setup Portals

The ESP32-CAM and ESP32-S3 rover sketches no longer require private Wi-Fi credentials to be edited into the code.

On first boot, or when saved Wi-Fi settings fail, use these temporary setup networks:

```text
Camera setup Wi-Fi: STASIS-CAM-SETUP
Rover setup Wi-Fi:  STASIS-ROVER-SETUP
Setup password:     stasis1234
Setup page:         http://192.168.4.1
```

The camera setup page asks for Wi-Fi SSID/password. The rover setup page asks for Wi-Fi SSID/password plus the laptop/server IP. Settings are saved in ESP32 flash and usually survive normal re-uploads.

## Important

The public repo does not contain your private Wi-Fi credentials. You still need to update the laptop server with the ESP32-CAM IP after the camera joins your network.

Read the full setup guide here:

```text
docs/README_ROVER_SYSTEM.md
```

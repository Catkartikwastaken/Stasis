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

ESP32-S3 power:

```text
7.4V Li-ion battery positive -> ESP32-S3 VIN
7.4V Li-ion battery negative -> ESP32-S3 GND
```

Do NOT use the ESP32-S3 5V pin for battery input. The 7.4V battery connects directly to VIN because the ESP32-S3 board has its own onboard regulator.

ESP32-S3 rover to MPU6050:

```text
GPIO 21  -> SDA
GPIO 22  -> SCL
3V3      -> VCC
GND      -> GND
```

ESP32-S3 rover to GY-271 compass:

```text
GPIO 21  -> SDA
GPIO 22  -> SCL
3V3      -> VCC
GND      -> GND
I2C      -> 0x1E
```

ESP32-S3 rover to HC-SR04 ultrasonic sensor:

```text
GPIO 33  -> Trig
GPIO 32  -> Echo
3V3      -> VCC
GND      -> GND
```

Power the HC-SR04 from 3.3V, not 5V, so the Echo signal does not damage the ESP32-S3.

ESP32-S3 rover to scanner servo:

```text
GPIO 13  -> Signal
5V       -> Power/red
GND      -> Ground/brown
```

Use a common ground between the ESP32-S3, motor driver, motor battery, sensors, and servo. If a motor spins backward, swap that motor's two output wires or invert that motor in code.

## Setup Portals

The ESP32-CAM and ESP32-S3 rover sketches no longer require private Wi-Fi credentials to be edited into the code.

On first boot, after a new firmware build, or when saved Wi-Fi settings fail, use these temporary setup networks:

```text
Camera setup Wi-Fi: STASIS-CAM-SETUP
Rover setup Wi-Fi:  STASIS-ROVER-SETUP
Setup password:     stasis1234
Setup page:         http://192.168.4.1
```

The camera setup page asks for Wi-Fi SSID/password. The rover setup page asks for Wi-Fi SSID/password plus the laptop/server IP. Settings are saved in ESP32 flash, but the current firmware intentionally reopens setup mode after a new build/upload so you can re-enter network details without editing code.

## If The Setup Wi-Fi Does Not Appear

If Serial Monitor only repeats `ESP-ROM`, `rst:0x8`, or `TG1WDT_SYS_RST` and never prints `ESP32-CAM booting...` or `ESP32-S3 rover booting...`, the sketch is not reaching `setup()`. Fix this before changing server code.

```text
1. Use Serial Monitor baud 115200.
2. In Arduino IDE, choose AI Thinker ESP32-CAM for the camera.
3. Choose ESP32S3 Dev Module, or the exact ESP32-S3 board you own, for the rover.
4. Erase flash once, then upload again.
5. Power the ESP32-CAM from a stable 5V supply, not weak 3.3V from a USB serial adapter.
6. For ESP32-CAM, keep GPIO0 connected to GND only while uploading. Disconnect GPIO0 from GND, then press RESET to run.
7. For the rover, test from USB power with motors, servo, and sensors unplugged first. Reconnect hardware after the setup Wi-Fi appears.
```

With the current firmware, a successful boot prints a firmware build line and reset reason before opening the setup hotspot.

## Important

The public repo does not contain your private Wi-Fi credentials. You still need to update the Windows laptop server with the ESP32-CAM IP after the camera joins your network.

Read the full setup guide here:

```text
docs/README_ROVER_SYSTEM.md
```

# Indoor Security Rover System

This repository contains a complete starter setup for the indoor security rover:

1. An ESP32-CAM streams video over MJPEG.
2. A laptop runs the Flask/Socket.IO vision and command server.
3. An ESP32-S3 rover connects to the laptop by WebSocket.
4. A browser dashboard sends map goals and displays alerts.

## File Locations

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

## How The Pieces Work Together

The ESP32-CAM firmware serves the camera stream here:

```text
http://<ESP32_CAM_IP>/stream
```

The laptop server reads that stream with OpenCV. The ESP32-S3 rover connects to the laptop at:

```text
ws://<SERVER_IP>:5000/ws/rover
```

After connecting, the rover sends:

```json
{"id":"esp32s3_rover","type":"rover"}
```

The dashboard connects by Socket.IO to:

```text
http://<SERVER_IP>:5000
```

When the dashboard sends `set_goal`, the server converts the clicked map point into a rover command:

```json
{"cmd":"goto","angle":45.2,"distance":30.5}
```

When the rover finishes, it sends:

```json
{"status":"goal_reached"}
```

When the vision model detects activity, the server saves an image in `alerts/`, emits `new_alert`, and sends this to the rover:

```json
{"cmd":"alert_buzzer"}
```

## No More Hardcoded Wi-Fi

The ESP32 sketches no longer store your private Wi-Fi SSID/password in the code. On first boot, or whenever saved Wi-Fi settings are missing or fail, each board opens its own setup hotspot.

Saved settings are stored in ESP32 flash memory with `Preferences`, so they usually survive normal sketch uploads. If you need to force setup again, erase the board flash from Arduino IDE or boot the board somewhere the saved Wi-Fi cannot connect.

## ESP32-CAM Setup Portal

Open this sketch in Arduino IDE:

```text
firmware/esp32cam/esp32_cam_mjpeg_stream/esp32_cam_mjpeg_stream.ino
```

Board:

```text
AI Thinker ESP32-CAM
```

Required libraries for the setup portal are included with the ESP32 Arduino core:

```text
DNSServer
Preferences
WebServer
WiFi
esp_camera
esp_http_server
```

After upload, if no saved Wi-Fi exists, connect your phone/laptop to:

```text
Wi-Fi network: STASIS-CAM-SETUP
Password: stasis1234
Setup page: http://192.168.4.1
```

Enter your home Wi-Fi SSID and password, then press **Save and Restart**.

After restart, open Serial Monitor at `115200` and copy the printed stream URL:

```text
Camera stream ready: http://<ESP32_CAM_IP>/stream
```

The sketch also prints the ESP32-CAM MAC address. You do not need to enter that MAC address into the ESP32-S3 rover sketch for this project. The ESP32-S3 needs the laptop/server IP, and the laptop server needs the ESP32-CAM IP.

Put the camera IP into:

```text
server/security_rover_server.py
server/security_rover_server_windows.py
server/templates/index.html if you want the served dashboard feed updated there
dashboard/rover_dashboard.html or dashboard/rover_dashboard_windows.html if you use the standalone dashboard
```

## ESP32-S3 Rover Setup Portal

Open this sketch in Arduino IDE:

```text
firmware/esp32s3/esp32s3_rover_ws.ino
```

Required Arduino libraries:

```text
Adafruit MPU6050
Adafruit Unified Sensor
ArduinoJson
WebSockets by Markus Sattler
```

The Wi-Fi/server settings are entered through a setup page instead of being hardcoded.

After upload, if no saved settings exist, connect your phone/laptop to:

```text
Wi-Fi network: STASIS-ROVER-SETUP
Password: stasis1234
Setup page: http://192.168.4.1
```

Enter:

```text
Your Wi-Fi SSID
Your Wi-Fi password
The laptop/server IP address running Flask on port 5000
```

Then press **Save and Restart**. The rover will reboot, join your Wi-Fi, and connect to:

```text
ws://<SERVER_IP>:5000/ws/rover
```

The rover expects:

```text
L9110S A-IA = GPIO 26
L9110S A-IB = GPIO 27
L9110S B-IA = GPIO 14
L9110S B-IB = GPIO 12
MPU6050 SDA = GPIO 21
MPU6050 SCL = GPIO 22
Buzzer = GPIO 33
```

Keep the rover still during startup while the gyro calibrates.

## Windows Laptop Version

Use this server on Windows:

```text
server/security_rover_server_windows.py
```

It uses CUDA if available, otherwise CPU.

Install dependencies from PowerShell:

```powershell
cd server
py -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements-windows.txt
```

Edit this line in `server/security_rover_server_windows.py`:

```python
ESP32_CAM_IP = "192.168.1.100"
```

Replace it with the IP printed by the ESP32-CAM Serial Monitor.

Run:

```powershell
python security_rover_server_windows.py
```

Open:

```text
http://<WINDOWS_LAPTOP_IP>:5000
```

If Windows asks about firewall access, allow Python on the private network. The ESP32 boards must be able to reach port `5000` on the laptop.

## Dashboard Options

The easiest dashboard is served by Flask:

```text
http://<WINDOWS_LAPTOP_IP>:5000
```

You can also open this standalone file:

```text
dashboard/rover_dashboard_windows.html
```

Before using the standalone file, edit:

```js
const WINDOWS_LAPTOP_IP = "<WINDOWS_LAPTOP_IP>";
const ESP32_CAM_IP = "<ESP32_CAM_IP>";
```

## Recommended Startup Order

1. Flash and power the ESP32-CAM.
2. Join `STASIS-CAM-SETUP`, open `http://192.168.4.1`, save Wi-Fi details, and let it restart.
3. Write down the ESP32-CAM IP from Serial Monitor.
4. Edit `ESP32_CAM_IP` in the Windows server.
5. Start `server/security_rover_server_windows.py`.
6. Flash and power the ESP32-S3 rover.
7. Join `STASIS-ROVER-SETUP`, open `http://192.168.4.1`, save Wi-Fi details and the laptop/server IP, and let it restart.
8. Open `http://<WINDOWS_LAPTOP_IP>:5000` in the browser.
9. Click the map to send a rover goal.

## Serial Monitor Troubleshooting

Use `115200` baud in Serial Monitor for both ESP32 boards.

If you see random symbols, the Serial Monitor baud rate is wrong.

If the ESP32-CAM shows `Camera init failed`, check:

```text
Board selected: AI Thinker ESP32-CAM
GPIO 0 disconnected from GND after upload
5V power is stable
Camera ribbon cable is seated correctly
PSRAM is enabled when the board menu offers it
```

If either board cannot connect to Wi-Fi, let the setup portal reopen by clearing flash or entering Wi-Fi details again. The router must support 2.4 GHz Wi-Fi.

If the ESP32-S3 rover cannot connect to the server, enter the laptop IP in the rover setup page, not the camera IP.

## Calibration Notes

The rover has no wheel encoders, so forward distance is open-loop and approximate.

Tune this in `esp32s3_rover_ws.ino`:

```cpp
const float DRIVE_MS_PER_CM = 50.0;
```

If the rover drives too far, lower it. If it stops short, raise it.

Tune turning with:

```cpp
const float TURN_KP = 5.0;
const float TURN_TOLERANCE_DEG = 5.0;
```

## Compatibility Checklist

```text
Camera stream endpoint:      /stream
Rover WebSocket endpoint:    /ws/rover
Rover ID:                    esp32s3_rover
Dashboard goal event:        set_goal
Server alert event:          new_alert
Server position event:       rover_position
Rover buzzer command:        {"cmd":"alert_buzzer"}
Rover navigation command:    {"cmd":"goto","angle":...,"distance":...}
```

## Verification Notes

The Python server files were syntax-checked earlier with:

```powershell
python -m py_compile .\security_rover_server.py .\security_rover_server_windows.py
```

Arduino compile verification requires the ESP32 Arduino board package. In this workspace, Arduino CLI currently has only `arduino:avr` installed. I tried installing `esp32:esp32`, but the `esp32:esp-x32@2601` toolchain download was cut off twice by the remote host before completion, so a local Arduino compile could not be completed here.

Install the ESP32 package in Arduino IDE if CLI download keeps failing:

```text
Boards Manager -> esp32 by Espressif Systems
```

Then compile with these board choices:

```text
ESP32-CAM: AI Thinker ESP32-CAM
ESP32-S3 rover: your exact ESP32-S3 Dev Module board
```

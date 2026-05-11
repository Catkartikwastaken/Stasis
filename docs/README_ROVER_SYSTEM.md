# Indoor Security Rover System

This folder contains a complete starter setup for the indoor security rover:

1. An ESP32-CAM streams video over MJPEG.
2. A laptop runs the Flask/Socket.IO vision and command server.
3. An ESP32-S3 rover connects to the laptop by WebSocket.
4. A browser dashboard sends map goals and displays alerts.

## File Locations

In this GitHub repository, the files are arranged like this:

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

The laptop server reads that same stream with OpenCV:

```python
ESP32_CAM_IP = "192.168.1.100"
STREAM_URL = f"http://{ESP32_CAM_IP}/stream"
```

The ESP32-S3 rover connects to the laptop server here:

```text
ws://<SERVER_IP>:5000/ws/rover
```

After connecting, the rover sends:

```json
{"id":"esp32s3_rover","type":"rover"}
```

The dashboard connects to the laptop server by Socket.IO:

```text
http://<SERVER_IP>:5000
```

When you click the map, the dashboard sends a `set_goal` event. The server converts that click into:

```json
{"cmd":"goto","angle":45.2,"distance":30.5}
```

and sends it to the rover. When the rover finishes, it sends:

```json
{"status":"goal_reached"}
```

When the vision model detects activity, the server saves an image in:

```text
alerts/alert_<timestamp>.jpg
```

Then it sends a `new_alert` event to the browser and sends this command to the rover:

```json
{"cmd":"alert_buzzer"}
```

## Windows Laptop Version

Use this version when the central laptop is running Windows:

```text
server/security_rover_server_windows.py
```

It uses CUDA if available, otherwise CPU.

Install Python packages from PowerShell:

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

Run the Windows server:

```powershell
python security_rover_server_windows.py
```

Open this in the browser:

```text
http://<WINDOWS_LAPTOP_IP>:5000
```

If Windows asks about firewall access, allow Python on your private network. The ESP32 boards must be able to reach port `5000` on the laptop.

## ESP32-CAM Setup

Open this sketch in Arduino IDE:

```text
firmware/esp32cam/esp32_cam_mjpeg_stream/esp32_cam_mjpeg_stream.ino
```

Board:

```text
AI Thinker ESP32-CAM
```

Wi-Fi settings are near the top:

```cpp
const char *WIFI_SSID = "StasisNet";
const char *WIFI_PASSWORD = "12345678";
```

Upload the sketch, open Serial Monitor at `115200`, and copy the printed stream URL:

```text
Camera stream ready: http://<ESP32_CAM_IP>/stream
```

The sketch also prints the ESP32-CAM MAC address. You do not need to enter that MAC address into the ESP32-S3 rover sketch for this project. The ESP32-S3 needs the laptop/server IP, and the laptop server needs the ESP32-CAM IP.

## ESP32-S3 Rover Setup

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

Update the server IP:

```cpp
const char *SERVER_IP = "192.168.1.10";
```

Use your Windows laptop IP address. Keep the WebSocket path as:

```cpp
const char *WEBSOCKET_PATH = "/ws/rover";
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

If the ESP32-CAM keeps printing dots after `Connecting to WiFi`, check:

```text
SSID and password
Router is 2.4 GHz, not 5 GHz only
Board is close enough to the router
```

If the ESP32-S3 rover cannot connect, update this line with the laptop IP, not the camera IP:

```cpp
const char *SERVER_IP = "192.168.1.10";
```

## Recommended Startup Order

1. Flash and power the ESP32-CAM.
2. Write down the ESP32-CAM IP from Serial Monitor.
3. Edit `ESP32_CAM_IP` in the Windows server.
4. Start `security_rover_server_windows.py`.
5. Edit `SERVER_IP` in the ESP32-S3 rover sketch.
6. Flash and power the ESP32-S3 rover.
7. Open `http://<WINDOWS_LAPTOP_IP>:5000` in the browser.
8. Click the map to send a rover goal.

## Calibration Notes

The rover has no wheel encoders, so forward distance is open-loop and approximate.

Tune this value in `esp32s3_rover_ws.ino`:

```cpp
const float DRIVE_MS_PER_CM = 50.0;
```

If the rover drives too far, lower it. If it stops short, raise it.

The turn controller uses the MPU6050 gyro Z axis:

```cpp
const float TURN_KP = 5.0;
const float TURN_TOLERANCE_DEG = 5.0;
```

If it turns too aggressively, lower `TURN_KP`. If it stops too early, lower `TURN_TOLERANCE_DEG`.

## Quick Compatibility Checklist

Use these exact matching values:

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

That is the glue that makes all files work hand in hand.

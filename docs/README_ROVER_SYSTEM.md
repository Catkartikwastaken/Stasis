# Indoor Security Rover System

This repository contains a complete starter setup for the indoor security rover:

1. An ESP32-CAM streams video over MJPEG.
2. A laptop runs the Flask/Socket.IO vision and command server.
3. An ESP32-S3 rover connects to the laptop by WebSocket.
4. A browser dashboard sends map goals and displays alerts.

## File Locations

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

When the vision model detects activity, the server saves an image in `alerts/` and emits `new_alert` to the dashboard. Physical sound alerts were removed from the rover hardware.

## Hardware Connections

The ESP32-CAM and ESP32-S3 rover do not connect directly to each other with wires. They both join the same 2.4 GHz Wi-Fi network and communicate through the laptop server.

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

The MPU6050 and GY-271 share the same I2C bus. The MPU6050 uses address `0x68`; the GY-271/HMC5883L compass uses address `0x1E`.

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

Use a common ground between the ESP32-S3, motor driver, motor battery, sensors, and servo. If a motor spins backward, swap that motor's two output wires or invert that motor in code. Use a separate motor supply when possible, because motor noise and voltage dips can reset the ESP32-S3.

## No More Hardcoded Wi-Fi

The ESP32 sketches no longer store your private Wi-Fi SSID/password in the code. On first boot, after a new firmware build, or whenever saved Wi-Fi settings are missing or fail, each board opens its own setup hotspot.

Saved settings are stored in ESP32 flash memory with `Preferences`, but the current firmware also stores a build ID. After a new upload, the build ID changes and setup mode opens again so you can re-enter network details without editing code.

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
firmware/esp32s3/esp32s3_rover_ws/esp32s3_rover_ws.ino
```

Required Arduino libraries:

```text
Adafruit MPU6050
Adafruit HMC5883 Unified
Adafruit Unified Sensor
ArduinoJson
ESP32Servo
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

If Serial Monitor only repeats bootloader lines such as `ESP-ROM`, `rst:0x8`, or `TG1WDT_SYS_RST`, and you never see `ESP32-CAM booting...` or `ESP32-S3 rover booting...`, the sketch is not reaching `setup()`. That is almost always power, boot-mode wiring, board selection, or corrupted flash state.

Do this first:

```text
1. Erase flash once, then upload the sketch again.
2. ESP32-CAM board: select AI Thinker ESP32-CAM.
3. ESP32-S3 rover board: select ESP32S3 Dev Module, or the exact board you own.
4. ESP32-CAM upload: connect GPIO0 to GND only while uploading.
5. ESP32-CAM run: disconnect GPIO0 from GND, then press RESET.
6. ESP32-CAM power: use stable 5V power. Many USB serial adapters cannot supply enough current.
7. ESP32-S3 test: power by USB with motors, servo, MPU6050, compass, and HC-SR04 unplugged. Reconnect hardware after the setup hotspot appears.
8. If the S3 only fails when motors/servo are connected, use a separate motor/servo supply with common GND.
```

With the current firmware, a successful boot prints a firmware build line and reset reason before it opens the setup hotspot. If you do not see those lines, keep debugging boot/power/board settings before changing Flask or WebSocket code.

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
Dashboard return event:      return_home
Dashboard scan event:        request_scan
Server alert event:          new_alert
Server position event:       rover_position
Rover scan command:          {"cmd":"scan"}
Rover navigation command:    {"cmd":"goto","angle":...,"distance":...}
```

## Verification Notes

The Python server files were syntax-checked earlier with:

```powershell
python -m py_compile .\security_rover_server.py .\security_rover_server_windows.py
```

Arduino CLI is installed at:

```text
C:\Windows\System32\arduino-cli.exe
```

The ESP32 Arduino core installed successfully:

```text
esp32:esp32 2.0.17
```

The required rover libraries were installed with Arduino CLI:

```text
Adafruit MPU6050
Adafruit HMC5883 Unified
Adafruit Unified Sensor
ArduinoJson
ESP32Servo
WebSockets
```

These compile checks passed from the repo root:

```text
arduino-cli compile --fqbn esp32:esp32:esp32cam firmware\esp32cam\esp32_cam_mjpeg_stream
arduino-cli compile --fqbn esp32:esp32:esp32s3 firmware\esp32s3\esp32s3_rover_ws
```

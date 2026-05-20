# Indoor Security Rover System

This repository contains a complete starter setup for the indoor security rover:

1. An ESP32-CAM streams video over MJPEG.
2. A laptop runs the Flask/Socket.IO vision and command server.
3. A Raspberry Pi 2B runs the Python rover client.
4. A browser dashboard sends map goals and displays alerts.

The ESP32-S3 rover firmware is kept in the repo as a legacy reference, but the active rover controller is now `rover/rpi2b/rover_client.py`.

## File Locations

```text
firmware/esp32cam/esp32_cam_mjpeg_stream/esp32_cam_mjpeg_stream.ino
firmware/esp32s3/esp32s3_rover_ws/esp32s3_rover_ws.ino      legacy reference only
rover/rpi2b/rover_client.py
rover/rpi2b/config.example.json
rover/rpi2b/requirements.txt
rover/rpi2b/README.md
rover/rpi2b/stasis-rover.service.example
server/security_rover_server.py
server/security_rover_server_windows.py
server/requirements.txt
server/requirements-windows.txt
server/templates/index.html
dashboard/rover_dashboard.html
dashboard/rover_dashboard_windows.html
docs/GEMMA_VISION.md
docs/README_ROVER_SYSTEM.md
```

## How The Pieces Work Together

The ESP32-CAM firmware serves the camera stream here:

```text
http://<ESP32_CAM_IP>/stream
```

The laptop server reads that stream with OpenCV. The Raspberry Pi rover connects to the laptop at:

```text
ws://<SERVER_IP>:5000/ws/rover
```

After connecting, the Pi sends:

```json
{"id":"rpi2b_rover","type":"rover"}
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

When Gemma detects activity, the server saves an image in `alerts/` and emits `new_alert` to the dashboard. Physical sound alerts are not part of the rover hardware. Gemma setup details live in `docs/GEMMA_VISION.md`.

## Raspberry Pi 2B Rover Responsibilities

The Python client replaces the major ESP32-S3 rover functions:

```text
Wi-Fi/server setup       -> config.json, CLI flags, or STASIS_SERVER_HOST
WebSocket registration   -> websocket-client
L9110S motor control     -> RPi.GPIO PWM
MPU6050 gyro yaw         -> smbus2 I2C
GY-271 compass heading   -> smbus2 I2C
HC-SR04 scan distance    -> RPi.GPIO timing
Scanner servo sweep      -> RPi.GPIO PWM
Telemetry heartbeat      -> JSON over WebSocket
Goto and scan commands   -> Python command worker
```

## Raspberry Pi Wiring

Default pin numbers use Raspberry Pi BCM numbering. You can change them in `rover/rpi2b/config.json`.

L9110S motor driver:

```text
BCM 5   -> Left motor forward input
BCM 6   -> Left motor reverse input
BCM 13  -> Right motor forward input
BCM 19  -> Right motor reverse input
GND     -> L9110S GND and motor battery negative
VM/VCC  -> Motor battery positive, matched to your motors/driver board
Motor A -> Left motor terminals
Motor B -> Right motor terminals
```

MPU6050 and GY-271/HMC5883L:

```text
BCM 2 / physical pin 3  -> SDA
BCM 3 / physical pin 5  -> SCL
3V3                     -> VCC
GND                     -> GND
MPU6050 address         -> 0x68
GY-271/HMC5883L address -> 0x1E
```

The MPU6050 and GY-271 share the same I2C bus.

HC-SR04 ultrasonic sensor:

```text
BCM 23 -> Trig
BCM 24 -> Echo
VCC    -> 5V or 3V3
GND    -> GND
```

Raspberry Pi GPIO is not 5V tolerant. If the HC-SR04 is powered from 5V, put a voltage divider or level shifter on Echo before it reaches BCM 24.

Scanner servo:

```text
BCM 18 -> Signal
5V     -> Power/red
GND    -> Ground/brown
```

Use a common ground between the Pi, motor driver, motor battery, sensors, and servo. Use a separate motor/servo supply when possible because motor noise and voltage dips can reboot the Pi.

## Raspberry Pi Setup

Enable I2C on the Pi:

```bash
sudo raspi-config
```

Open `Interface Options`, enable `I2C`, then reboot.

Install the rover client dependencies:

```bash
cd rover/rpi2b
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp config.example.json config.json
```

Edit `config.json`:

```json
{
  "server_host": "192.168.1.10",
  "rover_id": "rpi2b_rover"
}
```

Run the rover:

```bash
python rover_client.py --config config.json
```

You can also pass the server directly:

```bash
python rover_client.py --server 192.168.1.10
```

For a protocol-only test without GPIO/I2C hardware:

```bash
python rover_client.py --server 192.168.1.10 --simulate
```

To start the rover client automatically on boot, edit `rover/rpi2b/stasis-rover.service.example` so its paths match the repo location on your Pi, copy it to `/etc/systemd/system/stasis-rover.service`, then run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now stasis-rover
sudo systemctl status stasis-rover
```

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

Put the camera IP into:

```text
server/security_rover_server.py
server/security_rover_server_windows.py
server/templates/index.html if you want the served dashboard feed updated there
dashboard/rover_dashboard.html or dashboard/rover_dashboard_windows.html if you use the standalone dashboard
```

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

Gemma vision alerts use `google/gemma-4-E2B-it` through Hugging Face Transformers. If your environment needs Hugging Face authentication for model downloads, set a token:

```powershell
$env:HF_TOKEN = "hf_your_token_here"
$env:STASIS_VISION_REQUIRED = "true"
```

Useful vision settings:

```powershell
$env:STASIS_VISION_DEVICE = "cuda"
$env:STASIS_VISION_DEVICE_MAP = "none"
$env:STASIS_VISION_TORCH_DTYPE = "bfloat16"
$env:STASIS_ANALYSIS_INTERVAL_SECONDS = "2"
```

To test rover control without loading Gemma:

```powershell
$env:STASIS_VISION_ENABLED = "false"
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

If Windows asks about firewall access, allow Python on the private network. The Raspberry Pi must be able to reach port `5000` on the laptop.

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
4. Set `HF_TOKEN` on the laptop if Hugging Face authentication is needed.
5. Edit `ESP32_CAM_IP` in the Windows server.
6. Start `server/security_rover_server_windows.py`.
7. Power the Raspberry Pi rover.
8. Edit `rover/rpi2b/config.json` with the laptop/server IP.
9. Run `python rover_client.py --config config.json` on the Pi.
10. Open `http://<WINDOWS_LAPTOP_IP>:5000` in the browser.
11. Click the map to send a rover goal.

## Calibration Notes

The rover has no wheel encoders, so forward distance is open-loop and approximate.

Tune this in `rover/rpi2b/config.json`:

```json
{
  "motion": {
    "drive_ms_per_cm": 50.0
  }
}
```

If the rover drives too far, lower it. If it stops short, raise it.

Tune turning with:

```json
{
  "motion": {
    "turn_kp": 0.8,
    "turn_tolerance_deg": 5.0,
    "turn_min_pwm": 35.0,
    "turn_max_pwm": 85.0
  }
}
```

If turning oscillates, lower `turn_kp`. If turning is too weak, raise `turn_min_pwm` or `turn_kp`.

## Compatibility Checklist

```text
Camera stream endpoint:      /stream
Rover WebSocket endpoint:    /ws/rover
Primary rover ID:            rpi2b_rover
Legacy rover ID accepted:    esp32s3_rover
Dashboard goal event:        set_goal
Dashboard return event:      return_home
Dashboard scan event:        request_scan
Server alert event:          new_alert
Server position event:       rover_position
Rover scan command:          {"cmd":"scan"}
Rover stop command:          {"cmd":"stop"}
Rover navigation command:    {"cmd":"goto","angle":...,"distance":...}
```

## Troubleshooting

If the Pi cannot connect to the server:

```text
1. Confirm the laptop and Pi are on the same network.
2. Confirm the server is running on 0.0.0.0:5000.
3. Confirm Windows Firewall allows Python on the private network.
4. Confirm config.json server_host is the laptop IP, not the camera IP.
```

If I2C sensors are not detected:

```bash
sudo apt install -y i2c-tools
i2cdetect -y 1
```

Expected addresses:

```text
MPU6050:          0x68
GY-271/HMC5883L: 0x1E
```

If the rover reports `imu_error`, the Pi does not have a usable compass or MPU6050 heading source. Fix I2C wiring, enable I2C, or confirm the sensor addresses in `config.json`.

If motors move backward, swap the motor leads or swap the forward/reverse pins for that side in `config.json`.

If the Pi reboots when motors or the servo move, power motors and servo from a separate supply and keep grounds common.

## Verification Notes

The active Python rover client can be syntax-checked with:

```bash
python -m py_compile rover/rpi2b/rover_client.py
```

The laptop server files can be syntax-checked with:

```powershell
python -m py_compile .\server\security_rover_server.py .\server\security_rover_server_windows.py
```

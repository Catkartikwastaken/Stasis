# STASIS Forest Monitoring Rover System

This repository contains a complete starter setup for STASIS, a forest monitoring rover that will be demonstrated indoors in a forest-like environment:

1. A USB webcam connects to the laptop.
2. A laptop runs the Flask/Socket.IO vision and command server.
3. A Raspberry Pi 2B runs the Python rover client.
4. A browser dashboard sends map goals and displays alerts.

The Raspberry Pi client is the active high-level rover controller in this branch. Old embedded camera code has been fully removed from the ESP32-S3, and its firmware now serves exclusively as a low-level USB-to-Serial motor control delegator (serial-to-PWM bridge) for the L911S driver. This ensures precise PWM motor drive signals and offloads low-level timing tasks from the Raspberry Pi.

The demo does not depend on GPS. Navigation stays local: manual dashboard driving, clicked goals, return-to-home, obstacle avoidance, scan commands, and marker-directed patrols.

## File Locations

```text
rover/esp32_s3/stasis_motor_controller.ino
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

The laptop server captures the USB webcam with OpenCV and serves it here:

```text
http://<SERVER_IP>:5000/camera.mjpg
```

The Raspberry Pi rover connects to the laptop at:

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

When Gemma detects a relevant forest-monitoring event, the server saves an image in `alerts/` and emits `new_alert` to the dashboard. Target events include humans/intruders, animals, visible track or soil changes, fire/smoke/flame, and custom colored markers such as red strips. Gemma setup details live in `docs/GEMMA_VISION.md`.

The server accepts alerts only for these categories:

```text
human
animal
track
fire
marker
```

If Gemma returns a category outside that list, the server suppresses the alert.

## Raspberry Pi 2B Rover Responsibilities

The Python client handles the major rover-control functions on the Raspberry Pi:

```text
Wi-Fi/server setup       -> config.json, CLI flags, or STASIS_SERVER_HOST
WebSocket registration   -> websocket-client
Motor control (Option A) -> RPi.GPIO PWM direct connection to L911S
Motor control (Option B) -> SerialMotorDriver delegator over USB-serial to ESP32-S3
MPU6050 gyro yaw         -> smbus2 I2C
GY-271 compass heading   -> smbus2 I2C
HC-SR04 scan distance    -> RPi.GPIO timing
Scanner servo sweep      -> RPi.GPIO PWM
Telemetry heartbeat      -> JSON over WebSocket
Goto and scan commands   -> Python command worker
```

The default Pi config starts in minimal-wire mode:

```text
Direct motor control: enabled (Option A) or delegated serial control (Option B)
I2C heading sensors: disabled
Ultrasonic sensor: disabled
Scanner servo: disabled
Goto turning: timed open-loop fallback
```

Enable optional sensors and configure the active motor driving mode in `rover/rpi2b/config.json` only after the hardware is physically connected.

## Rover Wiring Diagrams

The default pin numbers use BCM numbering. You can change these allocations in `rover/rpi2b/config.json`. The rover supports two motor driving topologies: direct Pi control and delegated ESP32-S3 control.

### Option A: Direct Raspberry Pi GPIO Motor Control
Direct connection to the L911S/L9110S motor driver from Raspberry Pi BCM GPIO pins:

```text
BCM 5   -> A-IA / IA, left motor forward input
BCM 6   -> A-IB / IB, left motor reverse input
BCM 13  -> B-IA, right motor forward input
BCM 19  -> B-IB, right motor reverse input
GND     -> L911S/L9110S GND and motor battery negative
VM/VCC  -> Motor battery positive, matched to your motors/driver board
Motor A -> Left motor terminals
Motor B -> Right motor terminals
```

Some L911S boards label the two channels as `A-IA`, `A-IB`, `B-IA`, and `B-IB`. Smaller boards may label a single channel as only `IA` and `IB`; use that pair for the left motor channel and the second pair for the right motor channel.

### Option B: ESP32-S3 Delegated Motor Control (Recommended)
The Raspberry Pi communicates with the ESP32-S3 over a USB/UART Serial connection. The ESP32-S3 then drives the L911S H-Bridge.

**1. Pi-to-ESP32 Connection:**
- USB Cable connecting a USB port on the Raspberry Pi directly to the ESP32-S3's USB/UART Port (mounts as `/dev/ttyUSB0` or `/dev/ttyACM0` on the Pi, or `COMx` on Windows).

**2. ESP32-S3 to L911S Driver Wiring:**
```text
ESP32 Pin 4 (GPIO4) -> A-IA, left motor forward input
ESP32 Pin 5 (GPIO5) -> A-IB, left motor reverse input
ESP32 Pin 6 (GPIO6) -> B-IA, right motor forward input
ESP32 Pin 7 (GPIO7) -> B-IB, right motor reverse input
GND                 -> L911S GND and motor battery negative
VM/VCC              -> Motor battery positive
Motor A             -> Left motor terminals
Motor B             -> Right motor terminals
```

---

### Onboard I2C Sensors & Sonar Sweep Peripherals

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

Use a common ground between the Pi, ESP32-S3, motor driver, motor battery, sensors, and servo. Use a separate motor/servo supply when possible because motor noise and voltage dips can reboot the Pi.

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
  "rover_id": "rpi2b_rover",
  "hardware": {
    "direct_motor_control": false,
    "esp32_serial_control": true,
    "esp32_serial_port": "/dev/ttyUSB0",
    "esp32_baudrate": 115200,
    "i2c_enabled": false,
    "ultrasonic_enabled": false,
    "scanner_servo_enabled": false
  }
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
$env:STASIS_CAMERA_INDEX = "0"
$env:STASIS_CAMERA_WIDTH = "640"
$env:STASIS_CAMERA_HEIGHT = "480"
$env:STASIS_CAMERA_FPS = "15"
$env:STASIS_VISION_DEVICE = "cuda"
$env:STASIS_VISION_DEVICE_MAP = "none"
$env:STASIS_VISION_TORCH_DTYPE = "bfloat16"
$env:STASIS_ANALYSIS_INTERVAL_SECONDS = "2"
```

To test rover control without loading Gemma:

```powershell
$env:STASIS_VISION_ENABLED = "false"
```

If the wrong webcam opens, change `STASIS_CAMERA_INDEX` to `1` or `2`, then restart the server.

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
```

## Recommended Startup Order

1. Plug the USB webcam into the laptop.
2. Set `HF_TOKEN` on the laptop if Hugging Face authentication is needed.
3. Set `STASIS_CAMERA_INDEX` if the webcam is not camera `0`.
4. Start `server/security_rover_server_windows.py`.
5. Power the Raspberry Pi rover.
6. Edit `rover/rpi2b/config.json` with the laptop/server IP.
7. Run `python rover_client.py --config config.json` on the Pi.
8. Open `http://<WINDOWS_LAPTOP_IP>:5000` in the browser.
9. Confirm the webcam feed appears, then click the map to send a rover goal.

## Demo Behavior Targets

The dashboard and rover protocol now support the core demo actions:

```text
Manual dashboard control
Clicked map goals
Immediate stop
Return-to-home
Ultrasonic scan
Gemma-based event alerts
```

The dashboard includes red-strip search and go-to-red-strip controls. Gemma marker detections are stored against the rover's current map position, so the rover can drive back to the last seen strip when commanded. The next behavior layer should add richer patrol scripts around those stored marker points.

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
Camera stream endpoint:      /camera.mjpg
Rover WebSocket endpoint:    /ws/rover
Primary rover ID:            rpi2b_rover
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

# STASIS Forest Monitoring Rover

This repository contains the current working prototype for STASIS, a forest monitoring rover that is being demoed indoors in a forest-like test space.

The current architecture is Python-based: a laptop server captures a USB webcam with OpenCV, runs Gemma vision, serves the dashboard, and talks to a Raspberry Pi 2B Python rover client for motion control.

STASIS is aimed at autonomous and manual forest patrol demos: detecting humans/intruders, animals, soil or track changes, fire/smoke, and custom colored navigation markers such as red strips. GPS is intentionally out of scope for the indoor demo.

The server enforces that scope in code: Gemma alerts are accepted only for `human`, `animal`, `track`, `fire`, or `marker`. Other model output is suppressed so the project does not drift into unrelated indoor-security detections.

## What Is Included

```text
rover/esp32_s3/stasis_motor_controller.ino                  ESP32 S3 motor driver firmware
rover/rpi2b/rover_client.py                                 active rover controller
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
docs/PROJECT_BRIEF.md
```

## Network Connections

```text
Laptop server:          http://<SERVER_IP>:5000
Webcam feed:            http://<SERVER_IP>:5000/camera.mjpg
Rover WebSocket:        ws://<SERVER_IP>:5000/ws/rover
Raspberry Pi rover ID:  rpi2b_rover
Dashboard goal event:   set_goal
Alert event:            new_alert
Position event:         rover_position
```

Only the laptop and Raspberry Pi need to be on the same Wi-Fi network for the demo. The webcam plugs into the laptop, the laptop runs Gemma, and the Pi receives rover commands over WebSocket.

## Rover Hardware Plans (Pi Direct & ESP32-S3 Options)

Default BCM pin numbers are used for physical direct Pi connections, but the system now supports delegating motor control to a dedicated ESP32-S3 microcontroller to ensure high-accuracy PWM mapping and lower timing noise on the Pi.

### Option A: Direct Raspberry Pi 2B Motor Control
Direct connection to the L911S/L9110S motor driver from Raspberry Pi BCM GPIO pins:

```text
BCM 5   -> A-IA / IA, left motor forward input
BCM 6   -> A-IB / IB, left motor reverse input
BCM 13  -> B-IA, right motor forward input
BCM 19  -> B-IB, right motor reverse input
GND     -> L911S/L9110S GND and motor battery negative
VM/VCC  -> Motor battery positive, matched to your motors/driver board
```

### Option B: ESP32-S3 Delegated Motor Control (Recommended)
The Raspberry Pi communicates with the ESP32-S3 over a USB/UART Serial connection. The ESP32-S3 then drives the L911S H-Bridge.

**1. Pi-to-ESP32 Connection:**
- USB Cable connecting the Raspberry Pi USB port directly to the ESP32-S3's USB/UART Port (usually mounts as `/dev/ttyUSB0` or `/dev/ttyACM0` on the Pi, or `COMx` on Windows).

**2. ESP32-S3 to L911S Driver Wiring:**
```text
ESP32 Pin 4 (GPIO4) -> A-IA, left motor forward input
ESP32 Pin 5 (GPIO5) -> A-IB, left motor reverse input
ESP32 Pin 6 (GPIO6) -> B-IA, right motor forward input
ESP32 Pin 7 (GPIO7) -> B-IB, right motor reverse input
GND                 -> L911S GND and motor battery negative
VM/VCC              -> Motor battery positive
```

---

### Onboard Sensors & Peripherals

MPU6050 and GY-271/HMC5883L I2C sensors (connected to the active I2C bus on the Pi):

```text
BCM 2 / physical pin 3  -> SDA
BCM 3 / physical pin 5  -> SCL
3V3                     -> VCC
GND                     -> GND
MPU6050 address         -> 0x68
GY-271/HMC5883L address -> 0x1E
```

HC-SR04 ultrasonic sensor:

```text
BCM 23 -> Trig
BCM 24 -> Echo
VCC    -> 5V or 3V3
GND    -> GND
```

Raspberry Pi GPIO is not 5V tolerant. If the HC-SR04 is powered from 5V, use a voltage divider or level shifter on Echo before connecting it to BCM 24.

Scanner servo:

```text
BCM 18 -> Signal
5V     -> Servo power
GND    -> Ground
```

Use a common ground between the Raspberry Pi, ESP32-S3, motor driver, motor battery, sensors, and servo. Use a separate motor/servo supply where possible.

## Raspberry Pi Rover Setup

On the Pi, enable I2C with `sudo raspi-config`, then reboot.

```bash
cd rover/rpi2b
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp config.example.json config.json
```

Edit `config.json` and set `server_host` to the IP address of the laptop running the Flask server.

Run the rover client:

```bash
python rover_client.py --config config.json
```

For a protocol-only test on a laptop:

```bash
python rover_client.py --server <SERVER_IP> --simulate
```

## Laptop Server

Use this server on Windows:

```text
server/security_rover_server_windows.py
```

Install dependencies from PowerShell:

```powershell
cd server
py -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements-windows.txt
```

Gemma vision alerts use `google/gemma-4-E2B-it` through Hugging Face Transformers on the laptop. If your environment needs Hugging Face authentication for model downloads, set a token:

```powershell
$env:HF_TOKEN = "hf_your_token_here"
$env:STASIS_VISION_REQUIRED = "true"
```

To test rover control without loading Gemma:

```powershell
$env:STASIS_VISION_ENABLED = "false"
```

Select a webcam if the default camera is not the one you want:

```powershell
$env:STASIS_CAMERA_INDEX = "0"
$env:STASIS_CAMERA_WIDTH = "640"
$env:STASIS_CAMERA_HEIGHT = "480"
$env:STASIS_CAMERA_FPS = "15"
```

Run:

```powershell
python security_rover_server_windows.py
```

Open:

```text
http://<WINDOWS_LAPTOP_IP>:5000
```

## Command Protocol

The server sends rover commands over WebSocket:

```json
{"cmd":"goto","angle":45.2,"distance":30.5}
{"cmd":"scan"}
{"cmd":"stop"}
```

The Raspberry Pi rover sends:

```json
{"id":"rpi2b_rover","type":"rover"}
{"status":"ready"}
{"heading":92.4,"distance_traveled":18.0}
{"status":"goal_reached"}
{"type":"scan","data":[{"angle":0,"distance":77.5}]}
```

Read the full setup guide here:

```text
docs/README_ROVER_SYSTEM.md
```

Read the project assumptions and open hardware questions here:

```text
docs/PROJECT_BRIEF.md
```

Read the Gemma vision setup guide here:

```text
docs/GEMMA_VISION.md
```

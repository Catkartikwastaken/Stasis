# STASIS Forest Monitoring Rover

This repository contains the current working prototype for STASIS, a forest monitoring rover that is being demoed indoors in a forest-like test space.

The current architecture uses a laptop server for Gemma vision, an ESP32-CAM for the MJPEG camera stream, and a Raspberry Pi 2B Python client for the rover's high-level control loop. The ESP32-S3 firmware remains in the repo as the existing microcontroller path while the exact Pi/ESP32-S3 hardware split is finalized.

STASIS is aimed at autonomous and manual forest patrol demos: detecting humans/intruders, animals, soil or track changes, fire/smoke, and custom colored navigation markers such as red strips. GPS is intentionally out of scope for the indoor demo.

The server enforces that scope in code: Gemma alerts are accepted only for `human`, `animal`, `track`, `fire`, or `marker`. Other model output is suppressed so the project does not drift into unrelated indoor-security detections.

## What Is Included

```text
firmware/esp32cam/esp32_cam_mjpeg_stream/esp32_cam_mjpeg_stream.ino
firmware/esp32s3/esp32s3_rover_ws/esp32s3_rover_ws.ino      ESP32-S3 rover firmware path
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
ESP32-CAM camera:       http://<ESP32_CAM_IP>/stream
Laptop server:          http://<SERVER_IP>:5000
Rover WebSocket:        ws://<SERVER_IP>:5000/ws/rover
Raspberry Pi rover ID:  rpi2b_rover
Dashboard goal event:   set_goal
Alert event:            new_alert
Position event:         rover_position
```

The ESP32-CAM, Raspberry Pi rover, ESP32-S3, and laptop server should join the same Wi-Fi network for the demo. The ESP32-CAM streams video to the laptop, the laptop runs Gemma, and the Pi receives rover commands over WebSocket. If a USB webcam becomes available later, compare it against the ESP32-CAM before replacing the camera path.

## Raspberry Pi 2B Rover Hardware

Default pin numbers use Raspberry Pi BCM numbering.

The default Pi config is minimal-wire: direct motor control is enabled, but I2C sensors, ultrasonic, and the scanner servo start disabled. Enable only the hardware that is actually connected in `rover/rpi2b/config.json`.

L911S/L9110S motor driver:

```text
BCM 5   -> A-IA / IA, left motor forward input
BCM 6   -> A-IB / IB, left motor reverse input
BCM 13  -> B-IA, right motor forward input
BCM 19  -> B-IB, right motor reverse input
GND     -> L911S/L9110S GND and motor battery negative
VM/VCC  -> Motor battery positive, matched to your motors/driver board
```

MPU6050 and GY-271/HMC5883L I2C sensors:

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

Use a common ground between the Raspberry Pi, motor driver, motor battery, sensors, and servo. Use a separate motor/servo supply where possible.

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

## ESP32-CAM Setup Portal

The ESP32-CAM sketch does not require private Wi-Fi credentials in code. On first boot, after a new firmware build, or when saved Wi-Fi settings fail, use:

```text
Camera setup Wi-Fi: STASIS-CAM-SETUP
Setup password:     stasis1234
Setup page:         http://192.168.4.1
```

After the camera joins Wi-Fi, copy the printed stream IP into:

```text
server/security_rover_server.py
server/security_rover_server_windows.py
server/templates/index.html if you want the served dashboard feed updated there
dashboard/rover_dashboard.html or dashboard/rover_dashboard_windows.html if you use the standalone dashboard
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

Edit this line with the ESP32-CAM IP:

```python
ESP32_CAM_IP = "192.168.1.100"
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

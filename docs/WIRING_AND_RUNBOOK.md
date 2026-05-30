---
title: Wiring And Runbook
---

# STASIS Wiring And Runbook

This guide matches the current Raspberry Pi 2B rover code and `rover/rpi2b/config.json` pin names.

## Current Demo Hardware

Required:

- Raspberry Pi 2B
- USB webcam
- L911S / L9110S dual motor driver
- 2 DC motors
- Separate motor battery pack
- Windows laptop running the STASIS dashboard server

Supported but not required for the current direct-Pi setup:

- ESP32-S3 as a USB-Serial motor bridge

Optional:

- HC-SR04 ultrasonic distance sensor
- SG90-style scanner servo
- MPU6050 IMU
- HMC5883L/QMC5883L compass module

## Important Power Rules

- Do not power motors from the Raspberry Pi 5V pin.
- Use a separate motor battery connected to the L911S motor power input.
- Connect Raspberry Pi GND and L911S GND together. Without common ground, motor control will be unreliable.
- Raspberry Pi GPIO pins are 3.3V logic. Do not feed 5V sensor output directly into a GPIO pin.
- If using HC-SR04, put a voltage divider or level shifter on the Echo pin before Raspberry Pi GPIO.

## Raspberry Pi 2B Pin Map

The code uses BCM GPIO numbering, not physical board pin numbers.

| Function | BCM GPIO | Physical Pin |
| --- | ---: | ---: |
| Left motor forward | GPIO5 | Pin 29 |
| Left motor reverse | GPIO6 | Pin 31 |
| Right motor forward | GPIO13 | Pin 33 |
| Right motor reverse | GPIO19 | Pin 35 |
| Ultrasonic trigger | GPIO23 | Pin 16 |
| Ultrasonic echo | GPIO24 | Pin 18 |
| Scanner servo signal | GPIO18 | Pin 12 |
| I2C SDA | GPIO2 | Pin 3 |
| I2C SCL | GPIO3 | Pin 5 |
| 3.3V sensor power | 3V3 | Pin 1 or 17 |
| 5V power | 5V | Pin 2 or 4 |
| Ground | GND | Pin 6, 9, 14, 20, 25, 30, 34, or 39 |

## L911S Motor Driver Wiring

Use this for the current `direct_motor_control` mode. This is the mode currently used by the demo config.

| L911S Pin | Connect To |
| --- | --- |
| A-IA | Raspberry Pi GPIO5, physical pin 29 |
| A-IB | Raspberry Pi GPIO6, physical pin 31 |
| B-IA | Raspberry Pi GPIO13, physical pin 33 |
| B-IB | Raspberry Pi GPIO19, physical pin 35 |
| VCC / VM | Motor battery positive |
| GND | Motor battery negative and Raspberry Pi GND |
| Motor A output | Left DC motor |
| Motor B output | Right DC motor |

If left/right movement is reversed, swap the two wires of that motor or swap the matching forward/reverse GPIO values in the config.

## ESP32-S3 Motor Bridge Wiring

The repo still supports the ESP32-S3, but it is optional. It is not used for the current direct-Pi demo unless you enable `esp32_serial_control`.

Use the ESP32-S3 only if you want this topology:

```text
Raspberry Pi -> USB serial -> ESP32-S3 -> L911S -> motors
```

In this mode:

- The Raspberry Pi still runs the camera, object detection client, dashboard link, and high-level rover decisions.
- The ESP32-S3 only receives serial speed commands and generates PWM for the L911S motor driver.
- Do not wire the same L911S input pins to both the Raspberry Pi and ESP32-S3 at the same time.

### Raspberry Pi To ESP32-S3

| Raspberry Pi | ESP32-S3 |
| --- | --- |
| USB port | ESP32-S3 USB/UART port |

After connecting, the Pi usually sees the ESP32-S3 as:

```text
/dev/ttyUSB0
```

or:

```text
/dev/ttyACM0
```

Check with:

```bash
ls /dev/ttyUSB* /dev/ttyACM*
```

### ESP32-S3 To L911S

These pins match `rover/esp32_s3/stasis_motor_controller.ino`.

| ESP32-S3 GPIO | L911S Pin | Purpose |
| ---: | --- | --- |
| GPIO4 | A-IA | Left motor forward |
| GPIO5 | A-IB | Left motor reverse |
| GPIO6 | B-IA | Right motor forward |
| GPIO7 | B-IB | Right motor reverse |
| GND | GND | Common ground |

L911S power and motor wiring stays the same:

| L911S Pin | Connect To |
| --- | --- |
| VCC / VM | Motor battery positive |
| GND | Motor battery negative, ESP32-S3 GND, and Raspberry Pi GND |
| Motor A output | Left DC motor |
| Motor B output | Right DC motor |

### ESP32-S3 Firmware

Flash this file to the ESP32-S3:

```text
rover/esp32_s3/stasis_motor_controller.ino
```

Serial settings:

```text
Baud rate: 115200
Command format: M:left_speed,right_speed
Example: M:80,-80
Stop: M:0,0
```

### Pi Config For ESP32-S3 Mode

Set the hardware section like this:

```json
"hardware": {
  "direct_motor_control": false,
  "esp32_serial_control": true,
  "esp32_serial_port": "/dev/ttyUSB0",
  "esp32_baudrate": 115200
}
```

If your Pi shows `/dev/ttyACM0`, use:

```json
"esp32_serial_port": "/dev/ttyACM0"
```

For the current simplest demo, keep ESP32-S3 disabled:

```json
"hardware": {
  "direct_motor_control": true,
  "esp32_serial_control": false
}
```

## USB Webcam Wiring

No jumper wires are needed.

| Webcam | Connect To |
| --- | --- |
| USB cable | Raspberry Pi USB port |

The config uses:

```json
"camera": {
  "enabled": true,
  "index": 0
}
```

If the camera is not found, test on the Pi:

```bash
ls /dev/video*
```

## HC-SR04 Ultrasonic Sensor Wiring

This is optional. The current demo profile keeps it disabled until connected.

| HC-SR04 Pin | Connect To |
| --- | --- |
| VCC | 5V |
| GND | Raspberry Pi GND |
| TRIG | GPIO23, physical pin 16 |
| ECHO | GPIO24, physical pin 18 through a voltage divider / level shifter |

Config when connected:

```json
"hardware": {
  "ultrasonic_enabled": true
}
```

## Scanner Servo Wiring

This is optional. Use it only if the camera/sensor is mounted on a servo.

| Servo Wire | Connect To |
| --- | --- |
| Signal | GPIO18, physical pin 12 |
| VCC | External 5V servo supply |
| GND | External supply GND and Raspberry Pi GND |

Do not power a moving servo from the Raspberry Pi 5V pin if it causes resets.

Config when connected:

```json
"hardware": {
  "scanner_servo_enabled": true
}
```

## MPU6050 IMU Wiring

This is optional. It uses I2C.

| MPU6050 Pin | Connect To |
| --- | --- |
| VCC | 3.3V |
| GND | Raspberry Pi GND |
| SDA | GPIO2, physical pin 3 |
| SCL | GPIO3, physical pin 5 |

Config when connected:

```json
"hardware": {
  "i2c_enabled": true,
  "mpu6050_enabled": true
}
```

## HMC5883L / QMC5883L Compass Wiring

This is optional. It also uses I2C.

| Compass Pin | Connect To |
| --- | --- |
| VCC | 3.3V |
| GND | Raspberry Pi GND |
| SDA | GPIO2, physical pin 3 |
| SCL | GPIO3, physical pin 5 |

Config when connected:

```json
"hardware": {
  "i2c_enabled": true,
  "compass_enabled": true
}
```

## Minimal Demo Wiring

For the current working demo, wire only:

```text
Raspberry Pi USB -> webcam
GPIO5  -> L911S A-IA
GPIO6  -> L911S A-IB
GPIO13 -> L911S B-IA
GPIO19 -> L911S B-IB
Pi GND -> L911S GND
Motor battery + -> L911S motor VCC/VM
Motor battery - -> L911S GND
L911S motor outputs -> two DC motors
```

Leave ultrasonic, servo, MPU6050, and compass disabled unless they are physically connected.

Do not add ESP32-S3 wiring in this minimal mode. Add ESP32-S3 only if you switch to serial motor mode.

## Run The Windows Server

Open PowerShell on the Windows laptop:

```powershell
cd C:\Users\haris\Downloads\Stasis-main\Stasis\server
$env:STASIS_DETECTION_AUTHORITY="pi"
$env:STASIS_OBJECT_REVIEW_PROVIDER="fallback"
$env:STASIS_PI_IGNORE_LABELS=""
$env:STASIS_PI_MIN_OBJECT_CONFIDENCE="0.20"
$env:STASIS_PI_MIN_COMMON_OBJECT_CONFIDENCE="0.35"
python security_rover_server_object_detection.py
```

Find the laptop IP:

```powershell
ipconfig
```

Open the dashboard:

```text
http://<WINDOWS_LAPTOP_IP>:5000
```

## Run The Raspberry Pi Rover

Open terminal on the Pi:

```bash
cd ~/Documents/Stasis
git pull origin main

cd ~/Documents/Stasis/rover/rpi2b
source .venv/bin/activate
nano config.json
```

Set `server_host` to the Windows laptop IP:

```json
"server_host": "10.68.233.74"
```

Start the rover:

```bash
python rover_client_object_detection.py --config config.json
```

Good startup logs:

```text
Pi-side NCNN YOLO detector loaded
Pi-side COCO object detector loaded
Combined detector ready
WebSocket handshake successful
Streaming Pi webcam smoothly
```

## Enable Every Sensor

Use this only after the ultrasonic sensor, scanner servo, MPU6050, and compass are physically wired.

The rover is fault-tolerant in this mode. If a sensor is enabled in config but not physically detected, startup continues and the missing part is disabled. Camera streaming and object detection should still run.

```bash
cd ~/Documents/Stasis/rover/rpi2b
cp config.json config.before_all_sensors.json
cp profiles/demo_all_sensors_pi.json config.json
nano config.json
```

Set:

```json
"server_host": "<WINDOWS_LAPTOP_IP>"
```

Then run:

```bash
source .venv/bin/activate
python rover_client_object_detection.py --config config.json
```

Expected all-sensor startup logs:

```text
Direct GPIO motor driver setup complete
MPU6050 initialized
HMC5883L compass initialized
Streaming Pi webcam smoothly
Combined detector ready
WebSocket handshake successful
```

If something is missing, acceptable warning logs include:

```text
MPU6050 sensor not found on I2C bus; heading tracking disabled.
HMC5883L compass sensor not found on I2C bus; compass disabled.
Failed to configure Ultrasonic rangefinder.
Failed to configure SG90 scanner servo.
Direct GPIO motor driver unavailable; continuing without motor output.
ESP32-S3 serial motor controller unavailable; continuing without motor output.
```

Those warnings mean the connected parts still run, while missing parts are skipped.

If the servo and ultrasonic are enabled together, dashboard `scan` commands sweep the servo and read distance samples. If ultrasonic is enabled, forward driving stops when distance is below `obstacle_stop_distance_cm`.

## ESP32-S3 Or Direct Pi Motors

Choose exactly one motor mode:

```text
Option A: Raspberry Pi GPIO -> L911S
Option B: Raspberry Pi USB -> ESP32-S3 -> L911S
```

Do not connect both Raspberry Pi motor GPIO pins and ESP32-S3 motor GPIO pins to the L911S inputs at the same time.

The all-sensors profile uses Option A by default:

```json
"direct_motor_control": true,
"esp32_serial_control": false
```

To use ESP32-S3 motor control instead, first move the L911S input wires from the Pi GPIO pins to ESP32-S3 GPIO4/GPIO5/GPIO6/GPIO7, then change:

```json
"direct_motor_control": false,
"esp32_serial_control": true,
"esp32_serial_port": "/dev/ttyUSB0",
"esp32_baudrate": 115200
```

## Current Detection Setup

The current stable setup is:

```json
"backend": "combined",
"yolo_model_path": "models/best_ncnn_model",
"common_detection_enabled": true,
"common_target_classes": ["person", "cell phone"]
```

This means:

- Custom NCNN model detects demo objects and green strip.
- COCO detector detects person and cell phone.
- Dashboard receives both through the Pi WebSocket.

## Quick Troubleshooting

No dashboard:

```bash
ping <WINDOWS_LAPTOP_IP>
```

No Pi connection on dashboard:

```bash
grep server_host config.json
python rover_client_object_detection.py --config config.json
```

No camera:

```bash
ls /dev/video*
```

Motors do not move:

- Check common ground between Pi and L911S.
- Check motor battery voltage.
- Check BCM pin numbers, not physical pin numbers.
- Try swapping motor output wires if direction is reversed.

False detections:

- Raise `confidence_threshold`.
- Raise `min_box_area_percent`.
- Use better lighting.
- Keep trained objects closer and centered.

Slow detections:

- Use 320x240 camera resolution.
- Keep `upload_interval_seconds` around `0.5`.
- Set `common_detection_every_n` to `4` if COCO slows the Pi.

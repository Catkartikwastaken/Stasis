# STASIS Raspberry Pi 2B Rover Client

This Python client runs the Raspberry Pi 2B side of the STASIS rover. It connects to the existing STASIS Flask server at `ws://<SERVER_IP>:5000/ws/rover`, registers as `rpi2b_rover`, accepts `goto`, `scan`, and `stop` commands, drives the L911S/L9110S motor driver, reads optional MPU6050 and GY-271/HMC5883L sensors, scans with optional HC-SR04 and servo hardware, and sends telemetry back to the dashboard.

The USB webcam connects to the Raspberry Pi. The Pi captures frames with Python/OpenCV, sends them to the Windows laptop over the rover WebSocket, receives Gemma `vision_result` messages, and sends `vision_decision` back to the server/dashboard.

The default config is intentionally minimal-wire: the Pi drives motors directly, but I2C heading sensors, ultrasonic, and the scanner servo are disabled until you enable them. With no heading sensor, the client uses timed open-loop turns for the indoor demo.

## Raspberry Pi Setup

Use Raspberry Pi OS on the Pi 2B and enable I2C:

```bash
sudo raspi-config
```

Open `Interface Options`, enable `I2C`, then reboot.

Install dependencies:

```bash
cd rover/rpi2b
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Create a local config:

```bash
cp config.example.json config.json
```

Edit `server_host` to the IP address of the laptop running `server/security_rover_server_windows.py` or `server/security_rover_server.py`.

Keep the webcam section enabled for the real demo:

```json
{
  "camera": {
    "enabled": true,
    "index": 0,
    "width": 640,
    "height": 480,
    "upload_interval_seconds": 2.0
  }
}
```

If the Pi opens the wrong webcam, change `camera.index` to `1` or `2`.

Enable optional hardware and ESP32 serial motor control only when they are physically connected:

```json
{
  "hardware": {
    "direct_motor_control": false,
    "esp32_serial_control": true,
    "esp32_serial_port": "/dev/ttyUSB0",
    "esp32_baudrate": 115200,
    "i2c_enabled": true,
    "mpu6050_enabled": true,
    "compass_enabled": true,
    "ultrasonic_enabled": true,
    "scanner_servo_enabled": true
  }
}
```

Run the rover:

```bash
python rover_client.py --config config.json
```

For a laptop protocol test without GPIO hardware:

```bash
python rover_client.py --server 192.168.1.10 --simulate
```

To run the client automatically on boot, edit `stasis-rover.service.example` so the paths match where this repo lives on your Pi, copy it to `/etc/systemd/system/stasis-rover.service`, then run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now stasis-rover
sudo systemctl status stasis-rover
```

## Wiring Diagrams

The rover supports two motor driving methods: direct GPIO control and mediated ESP32-S3 control.

### Option A: Direct Raspberry Pi GPIO L911S Control
Uses Raspberry Pi BCM GPIO pin allocations:

```text
BCM 5   -> A-IA / IA, left motor forward input
BCM 6   -> A-IB / IB, left motor reverse input
BCM 13  -> B-IA, right motor forward input
BCM 19  -> B-IB, right motor reverse input
GND     -> L911S/L9110S GND and motor battery negative
VM/VCC  -> Motor battery positive, matched to your motors/driver board
```

### Option B: ESP32-S3 Mediated L911S Control (Recommended)
Raspberry Pi communicates with the ESP32-S3 via USB-Serial. The ESP32-S3 drives the H-bridge directly:

**1. USB Link:**
- USB port of the Raspberry Pi 2B connected via USB cable to the ESP32-S3's UART/USB port.

**2. ESP32-S3 to L911S Wiring:**
```text
ESP32 Pin 4 (GPIO4) -> A-IA, left motor forward input
ESP32 Pin 5 (GPIO5) -> A-IB, left motor reverse input
ESP32 Pin 6 (GPIO6) -> B-IA, right motor forward input
ESP32 Pin 7 (GPIO7) -> B-IB, right motor reverse input
GND                 -> L911S GND and motor battery negative
VM/VCC              -> Motor battery positive
```

---

### Onboard I2C Sensors & Sonar Sweep Peripherals

I2C sensors:

```text
BCM 2 / physical pin 3  -> SDA
BCM 3 / physical pin 5  -> SCL
3V3                     -> MPU6050 VCC and GY-271 VCC
GND                     -> MPU6050 GND and GY-271 GND
MPU6050 address         -> 0x68
GY-271/HMC5883L address -> 0x1E
```

HC-SR04 ultrasonic sensor:

```text
BCM 23 -> Trig
BCM 24 -> Echo
5V or 3V3 -> VCC
GND -> GND
```

Raspberry Pi GPIO is not 5V tolerant. If the HC-SR04 is powered from 5V, put a voltage divider or level shifter on Echo before it reaches BCM 24.

Scanner servo:

```text
BCM 18 -> Signal
5V     -> Servo power
GND    -> Ground
```

Use a common ground between the Pi, motor driver, motor battery, sensors, and servo. Use a separate motor/servo supply where possible because motor noise and voltage dips can reboot the Pi.

## Tuning

Open-loop distance and minimal-wire turning are approximate because the rover has no wheel encoders. Tune these values in `config.json`:

```json
{
  "hardware": {
    "open_loop_turn_degrees_per_second": 90.0
  },
  "motion": {
    "drive_ms_per_cm": 50.0,
    "drive_pwm": 70.0,
    "turn_kp": 0.8,
    "turn_tolerance_deg": 5.0
  }
}
```

If the rover drives too far, lower `drive_ms_per_cm`. If it stops short, raise it. If turning oscillates, lower `turn_kp`; if it turns too slowly, raise `turn_kp` or `turn_min_pwm`.

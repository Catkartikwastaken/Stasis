# STASIS Raspberry Pi 2B Rover Client

This Python client replaces the ESP32-S3 rover firmware. It connects to the existing STASIS Flask server at `ws://<SERVER_IP>:5000/ws/rover`, registers as `rpi2b_rover`, accepts `goto` and `scan` commands, drives the L9110S motor driver, reads the MPU6050 and GY-271/HMC5883L sensors, scans with the HC-SR04 and servo, and sends telemetry back to the dashboard.

The ESP32-CAM can still be used for the MJPEG camera stream. This client replaces only the ESP32-S3 rover controller.

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

## Wiring

The default config uses Raspberry Pi BCM pin numbers.

L9110S motor driver:

```text
BCM 5   -> Left motor forward input
BCM 6   -> Left motor reverse input
BCM 13  -> Right motor forward input
BCM 19  -> Right motor reverse input
GND     -> L9110S GND and motor battery negative
VM/VCC  -> Motor battery positive, matched to your motors/driver board
```

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

Open-loop distance is still approximate because the rover has no wheel encoders. Tune these values in `config.json`:

```json
{
  "motion": {
    "drive_ms_per_cm": 50.0,
    "drive_pwm": 70.0,
    "turn_kp": 0.8,
    "turn_tolerance_deg": 5.0
  }
}
```

If the rover drives too far, lower `drive_ms_per_cm`. If it stops short, raise it. If turning oscillates, lower `turn_kp`; if it turns too slowly, raise `turn_kp` or `turn_min_pwm`.

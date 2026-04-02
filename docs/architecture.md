# STASIS — System Architecture

## Overview

STASIS uses a three-node architecture with ESP-NOW as the primary wireless protocol between rover and station, and UART for the Pi-to-C3 bridge.

## Communication Flow

```
[ESP32-S3 Rover] ←—ESP-NOW/BLE—→ [ESP32-C3 Mini] ←—UART 9600—→ [Raspberry Pi]
       ↑                                                              ↓
  [ESP32-CAM]                                                   [Flask Server]
  UART 115200                                                        ↓
                                                              [Web Dashboard]
                                                            Socket.IO + REST
```

## Node A — Rover Unit

### ESP32-S3 (Main Controller)
- 6-state machine: IDLE → NAVIGATING → PATROLLING → RETURNING → STUCK → CHARGING → EMERGENCY
- Sensors: GPS (NEO-6M), IMU (MPU6050), Temp (DS18B20), Battery ADC
- Motor control: 4x DC motors via L298N/L293D with differential drive
- Path learning: GPS waypoints stored in NVS flash with geohash indexing
- Geofencing: Ray-casting point-in-polygon at 1Hz
- Communication: ESP-NOW to station, UART to ESP32-CAM

### ESP32-CAM (Detection Module)
- Two-stage detection: Frame differencing → Person classifier
- MJPEG HTTP stream on port 81 (15fps max)
- Detection events sent as JSON over UART to ESP32-S3
- 30-second cooldown between detections

## Node B — Charging Station

### Raspberry Pi Zero W
- Flask + Flask-SocketIO server
- SQLite database (telemetry, alerts, geofences, paths, reports)
- Daily PDF report generation via fpdf2
- UART communication to ESP32-C3 at 9600 baud

### ESP32-C3 Mini
- WiFi Access Point (STASIS_NET) or STA mode
- TCP-UART bridge for web traffic
- ESP-NOW relay: receives rover telemetry, forwards to Pi as JSON
- GPIO: charging relay, emergency stop signal

## ESP-NOW Packet Types

| Type | Code | Direction | Size | Purpose |
|------|------|-----------|------|---------|
| Telemetry | 0x01 | Rover→Station | ~25 bytes | GPS, battery, IMU, state |
| Command | 0x02 | Station→Rover | ~85 bytes | Navigation, geofence |
| Alert | 0x03 | Rover→Station | ~4110 bytes | Detection with image |
| Image Chunk | 0x04 | Rover→Station | ~243 bytes | Base64 image fragments |

## Database Schema

- **telemetry** — Time-series GPS, battery, temperature, IMU, state
- **alerts** — Detections with type, GPS, image, acknowledgement
- **geofences** — Named polygons with active flag
- **paths** — Learned waypoint sequences with geohash keys
- **reports** — Daily PDF summaries
- **settings** — Key-value configuration store

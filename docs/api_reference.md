# STASIS — REST API Reference

Base URL: `http://<host>:5000/api/v1`

## Status

### `GET /status`
Returns rover health snapshot.

**Response:**
```json
{
  "connected": true,
  "state": "PATROLLING",
  "state_code": 2,
  "lat": 12.9716,
  "lon": 77.5946,
  "battery_voltage": 3.85,
  "battery_percent": 61,
  "temperature": 28.5,
  "is_charging": false,
  "battery_low": false,
  "server_version": "1.0.0",
  "uptime": 3600
}
```

## Telemetry

### `GET /telemetry?limit=100`
Returns recent telemetry records.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| limit | int | 100 | Max records to return |

## Alerts

### `GET /alerts`
Returns all alerts (filterable).

| Param | Type | Description |
|-------|------|-------------|
| type | string | Filter: HUMAN, STUCK, LOW_BATTERY, TILT |
| limit | int | Max records |

### `POST /alerts/<id>/ack`
Acknowledge an alert.

**Body:** `{ "notes": "False positive" }`

## Geofences

### `GET /geofences`
List all geofence configurations.

### `POST /geofences`
Create a new geofence.

**Body:**
```json
{
  "name": "North Forest",
  "polygon": [
    { "lat": 12.97, "lon": 77.59 },
    { "lat": 12.98, "lon": 77.59 },
    { "lat": 12.98, "lon": 77.60 },
    { "lat": 12.97, "lon": 77.60 }
  ]
}
```

### `DELETE /geofences/<id>`
Delete a geofence.

## Commands

### `POST /commands/goto`
Send rover to GPS coordinates.

**Body:** `{ "lat": 12.975, "lon": 77.595 }`

### `POST /commands/stop`
Emergency stop.

### `POST /commands/return`
Return to charging station.

### `POST /commands/resume`
Resume patrol after stuck event.

## Reports

### `GET /reports`
List daily reports.

### `GET /reports/<YYYY-MM-DD>/pdf`
Download PDF report for a specific date.

## Camera

### `GET /stream/url`
Returns ESP32-CAM MJPEG stream URL.

## Settings

### `GET /settings`
Retrieve all settings.

### `POST /settings`
Save settings (key-value pairs in body).

## Socket.IO Events

### Server → Client
| Event | Payload | Description |
|-------|---------|-------------|
| `telemetry` | Telemetry object | Every 2 seconds |
| `alert` | Alert object | New detection/stuck/battery |
| `rover_state` | State object | State machine change |
| `connection` | `{status: "lost"}` | Rover connection lost |

### Client → Server
| Event | Payload | Description |
|-------|---------|-------------|
| `command` | `{command, lat?, lon?}` | Send rover command |
| `ack_alert` | `{id, notes?}` | Acknowledge alert |

# STASIS Project Brief

STASIS is a forest monitoring rover. The first demo will happen indoors in a forest-like test space, so the system should behave like a patrol robot without depending on GPS.

## Current Mission

The rover should patrol a test area, watch the camera feed, and notify the dashboard when Gemma sees something important.

Primary detection targets:

```text
Humans/intruders
Animals or wildlife stand-ins
Soil changes, tracks, footprints, trails, or disturbed ground
Fire, smoke, or flame-like hazards
Custom colored markers or strips, especially red strips
```

Intruders are classified under the `human` category. Ordinary indoor doors and windows are not target classes for this project.

## Demo Hardware Plan

Current hardware assumptions:

```text
Laptop              -> Flask/Socket.IO server, dashboard, Gemma model
Raspberry Pi 2B     -> High-level rover client, motion, scan, telemetry
ESP32-CAM           -> Current MJPEG camera stream
ESP32-S3            -> Still available for embedded rover duties while the split is finalized
L911S motor driver  -> A-IA/A-IB and B-IA/B-IB motor inputs
Sensors             -> Obstacle avoidance, heading, scan, and demo telemetry
```

The ESP32-CAM should stay in the design for now. If a webcam becomes available, compare image quality, latency, setup complexity, and reliability before replacing the ESP32-CAM.

The current code defaults to a minimal-wire Raspberry Pi setup: motors can be driven directly, but optional I2C heading sensors, ultrasonic, and servo scanning are disabled until explicitly enabled in config. This keeps the first demo close to the current component limit instead of assuming extra boards and jumper wires.

## Behavior Targets

STASIS should support:

```text
Autonomous patrol scripts
Manual dashboard controls
Clicked map goals
Return-to-home
Obstacle avoidance
Human/intruder alerts
Animal alerts
Track and soil-change alerts
Fire alerts
Custom marker search and marker-directed patrol
```

For the colored-strip demo, the rover should be able to scan for a requested strip, remember where it was found, and later drive back to that strip when commanded.

The server now stores marker detections from Gemma against the rover's current map position. The dashboard can request a red-strip search and can command the rover back to the last seen red strip.

## Open Decisions

These details should be confirmed before the next hardware-specific implementation pass:

```text
Which board controls the L911S inputs: Raspberry Pi or ESP32-S3
Exact sensor list and which board each sensor connects to
Final ESP32-S3 role after the Raspberry Pi client is added
Whether a webcam is available and worth replacing the ESP32-CAM
Marker colors, marker names, and what action each marker should trigger
Indoor demo arena size and expected patrol route shape
```

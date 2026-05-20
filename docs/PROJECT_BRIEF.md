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
USB webcam          -> Camera input captured by laptop Python/OpenCV
Raspberry Pi 2B     -> High-level rover client, motion, scan, telemetry
L911S motor driver  -> A-IA/A-IB and B-IA/B-IB motor inputs
Sensors             -> Obstacle avoidance, heading, scan, and demo telemetry
```

The old embedded camera path has been removed. The laptop now captures the webcam directly with OpenCV and serves the dashboard camera feed from `/camera.mjpg`.

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
Exact sensor list and which board each sensor connects to
Marker colors, marker names, and what action each marker should trigger
Indoor demo arena size and expected patrol route shape
```

# Mounting Notes

## Rover Assembly

### Chassis Layout
- Mount ESP32-S3 centrally on top deck
- ESP32-CAM at the front, angled slightly downward (~10°)
- Motor drivers underneath the chassis plate
- Battery pack at rear (counterbalance for camera weight)
- GPS antenna on top with clear sky view
- LCD display visible from above

### Wiring Tips
1. Keep motor wires separate from signal wires
2. Use shielded cable for UART between S3 and CAM
3. Add ferrite beads on motor power lines to reduce EMI
4. Secure all connectors with hot glue for vibration resistance
5. Use a cable management system (zip ties, cable channels)

### Waterproofing (Optional)
- Conformal coating on PCBs
- Silicone seal around sensor openings
- IP65 enclosure for electronics compartment
- Waterproof connectors for external sensors

## Charging Station Assembly

- Raspberry Pi mounted in a case with ventilation
- ESP32-C3 Mini nearby with antenna clearance
- Charging contacts aligned with rover docking position
- Guide rails or magnetic alignment for autonomous docking

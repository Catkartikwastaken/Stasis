# STASIS — Bill of Materials

## Rover Unit (Node A)

| # | Component | Model/Spec | Qty | Notes |
|---|-----------|-----------|-----|-------|
| 1 | ESP32-S3 | ESP32-S3-WROOM-1 DevKit | 1 | Main controller, 8MB flash recommended |
| 2 | ESP32-CAM | AI-Thinker with OV2640 | 1 | 2MP camera, PSRAM required |
| 3 | Motor Driver | L298N Dual H-Bridge | 2 | One per motor pair, or single L293D quad |
| 4 | DC Motors | TT Gear Motor 3-6V | 4 | With wheels, ~200 RPM |
| 5 | GPS Module | NEO-6M with antenna | 1 | UART, external ceramic antenna |
| 6 | IMU Sensor | MPU6050 (GY-521) | 1 | I2C accelerometer + gyroscope |
| 7 | Temp Sensor | DS18B20 (waterproof) | 1 | OneWire, -55°C to +125°C |
| 8 | LCD Display | I2C 20x4 or 16x2 (HD44780) | 1 | Address 0x27 |
| 9 | Passive Buzzer | 5V passive buzzer | 1 | For audio alerts |
| 10 | Battery | 18650 Li-ion 3.7V | 2-4 | With holder and BMS |
| 11 | Voltage Regulator | LM7805 or Buck Converter | 1 | 5V regulated output |
| 12 | Resistors | 100kΩ (1/4W) | 2 | For battery voltage divider |
| 13 | Resistor | 4.7kΩ (1/4W) | 1 | DS18B20 pull-up |
| 14 | Chassis | 4WD Robot Car Kit | 1 | Acrylic or aluminum frame |
| 15 | Jumper Wires | Male-Male, Male-Female | ~40 | Various lengths |

## Charging Station (Node B)

| # | Component | Model/Spec | Qty | Notes |
|---|-----------|-----------|-----|-------|
| 16 | Raspberry Pi | Zero W | 1 | With header pins |
| 17 | ESP32-C3 | ESP32-C3 Mini Module | 1 | WiFi bridge |
| 18 | Relay Module | 5V Single Channel | 1 | For charging control |
| 19 | Power Supply | 5V 3A USB adapter | 1 | For Pi + C3 |
| 20 | SD Card | 16GB+ microSD | 1 | For Pi OS + data |
| 21 | USB Cable | Micro USB | 1 | Pi power |
| 22 | Charging Circuit | TP4056 with protection | 1 | 18650 Li-ion charger |

## Tools Required

- Soldering iron + solder
- Wire strippers
- Multimeter
- USB cables (USB-C, Micro USB)
- Computer with Arduino IDE
- FTDI adapter (for ESP32-CAM programming)

## Estimated Total Cost

| Category | Estimated Cost (USD) |
|----------|---------------------|
| Rover Electronics | ~$45-60 |
| Rover Mechanical | ~$15-25 |
| Charging Station | ~$25-35 |
| Tools & Supplies | ~$20-30 |
| **Total** | **~$105-150** |

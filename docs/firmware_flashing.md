# STASIS — Firmware Flashing Guide

## Requirements

- **Arduino IDE 2.x** or **PlatformIO**
- **ESP32 Arduino Core 2.x** (Board Manager URL: `https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json`)
- USB cables for each ESP32 module

## Required Libraries

Install via Arduino Library Manager:
- `ArduinoJson` by Benoit Blanchon (v6.x)
- `LiquidCrystal_I2C` by Frank de Brabander
- ESP-NOW and WiFi are included in ESP32 Arduino Core

## ESP32-S3 (Main Rover Controller)

1. **Board**: Select `ESP32S3 Dev Module`
2. **Settings**:
   - Flash Size: 4MB (or 8MB/16MB depending on module)
   - Partition Scheme: Default
   - PSRAM: Enabled (if available)
   - Upload Speed: 921600
3. **Open**: `firmware/esp32s3/main.ino`
4. **Upload**: Connect via USB and upload
5. **Verify**: Open Serial Monitor at 115200 baud — should see initialization messages

## ESP32-CAM (AI-Thinker)

1. **Board**: Select `AI Thinker ESP32-CAM`
2. **Settings**:
   - Flash Size: 4MB
   - Partition Scheme: Huge APP (3MB No OTA)
   - PSRAM: Enabled
   - Upload Speed: 115200
3. **Programmer**: Connect FTDI adapter:
   - FTDI TX → CAM U0RXD
   - FTDI RX → CAM U0TXD
   - GND → GND
   - 5V → 5V
   - GPIO0 → GND (for programming mode)
4. **Open**: `firmware/esp32cam/main.ino`
5. **Upload**: Press RST while GPIO0 is grounded, then upload
6. **Disconnect** GPIO0 from GND and reset to run normally

## ESP32-C3 Mini

1. **Board**: Select `ESP32C3 Dev Module`
2. **Settings**:
   - Flash Size: 4MB
   - USB CDC On Boot: Enabled
   - Upload Speed: 921600
3. **Open**: `firmware/esp32c3/main.ino`
4. **Upload**: Connect via USB-C and upload
5. **Verify**: Serial Monitor at 115200 — should see WiFi AP creation

## Updating MAC Addresses

After flashing all modules, note each module's MAC address from the serial output and update:
- `firmware/esp32s3/config.h` → `STATION_MAC`
- `firmware/esp32c3/config.h` → `ROVER_MAC`

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Upload fails | Check correct port, press BOOT button during upload |
| ESP32-CAM won't upload | Ensure GPIO0 is grounded, use 115200 baud |
| No serial output | Check baud rate matches (115200) |
| WiFi not starting | Verify Arduino ESP32 Core version ≥ 2.0.0 |
| Camera init fails | Check PSRAM is enabled in board settings |

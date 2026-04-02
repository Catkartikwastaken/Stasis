# Changelog

All notable changes to STASIS are documented here.

## [1.0.0] - 2026-03-31

### Added
- ESP32-S3 rover firmware with 6-state machine
- 4-motor differential drive with L298N/L293D support
- NEO-6M GPS handler with NMEA parsing
- MPU6050 IMU with stuck/tilt detection
- DS18B20 temperature monitoring
- Path learning with geohash-indexed NVS storage
- Geofence navigation with ray-casting algorithm
- ESP-NOW communication with chunked image transfer
- Non-blocking buzzer alert sequences
- I2C LCD with rotating status screens
- ESP32-CAM human detection pipeline (motion + heuristic classifier)
- MJPEG HTTP stream server on port 81
- ESP32-C3 Mini WiFi bridge with TCP-UART relay
- Flask + Flask-SocketIO backend server
- SQLite database for telemetry, alerts, geofences, paths, reports
- Daily PDF report generation with fpdf2
- Smart charging controller with scheduled windows
- React 18 dashboard with Tailwind CSS
- Real-time telemetry charts with Recharts
- Interactive Leaflet map with geofence editor
- Alert modal with browser notifications
- Chat-style command interface
- Full REST API and Socket.IO events
- Comprehensive documentation (architecture, wiring, API, setup, flashing)
- Pi setup script with systemd service
- Dashboard build script

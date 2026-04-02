# STASIS — Setup Guide

## Prerequisites

- Raspberry Pi Zero W with Raspberry Pi OS Lite
- Python 3.10+ installed on the Pi
- Arduino IDE 2.x or PlatformIO
- ESP32 Arduino Core 2.x installed
- Node.js 18+ (for building the dashboard)

## 1. Raspberry Pi Setup

### Automated Setup
```bash
git clone https://github.com/your-org/stasis-rover.git
cd stasis-rover
chmod +x scripts/install_pi.sh
./scripts/install_pi.sh
```

### Manual Setup
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python dependencies
sudo apt install -y python3-pip python3-venv python3-dev

# Create virtual environment
cd server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create data directories
sudo mkdir -p /var/stasis/reports
sudo chown -R pi:pi /var/stasis

# Create .env file
cp .env.example .env
# Edit with your settings
nano .env

# Enable UART on Pi
sudo raspi-config
# → Interface Options → Serial Port
# → Login shell: No
# → Serial hardware: Yes
# Reboot
```

### Run as Service
```bash
sudo cp scripts/stasis.service /etc/systemd/system/
sudo systemctl enable stasis
sudo systemctl start stasis
```

## 2. Build Dashboard

```bash
cd dashboard
npm install
npm run build
# Output goes to server/public/
```

## 3. Flash Firmware

See [`docs/firmware_flashing.md`](firmware_flashing.md) for detailed instructions.

## 4. Configure

### Environment Variables (server/.env)
```
STASIS_HOST=0.0.0.0
STASIS_PORT=5000
STASIS_DB=/var/stasis/stasis.db
STASIS_UART=/dev/ttyS0
STASIS_STATION_LAT=12.9716
STASIS_STATION_LON=77.5946
STASIS_CAM_URL=http://192.168.4.2:81/stream
```

### ESP32-C3 WiFi
Edit `firmware/esp32c3/config.h`:
- Set `WIFI_MODE_AP` to 1 for Access Point mode
- Set SSID/password for STA mode if connecting to existing network

### MAC Addresses
Update the MAC addresses in firmware config files with the actual MAC addresses of your ESP32 modules.

## 5. Connect & Test

1. Power on the charging station (Pi + ESP32-C3)
2. Connect to STASIS_NET WiFi
3. Open `http://192.168.4.1:5000` in browser
4. Power on the rover
5. Verify telemetry appears on dashboard

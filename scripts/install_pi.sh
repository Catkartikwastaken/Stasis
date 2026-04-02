#!/bin/bash
# STASIS — Raspberry Pi Setup Script
# Run as: sudo ./install_pi.sh

set -e

echo "========================================"
echo "  STASIS — Raspberry Pi Setup"
echo "========================================"

# Update system
echo "[1/6] Updating system..."
sudo apt update && sudo apt upgrade -y

# Install dependencies
echo "[2/6] Installing dependencies..."
sudo apt install -y python3-pip python3-venv python3-dev git

# Create directories
echo "[3/6] Creating directories..."
sudo mkdir -p /var/stasis/reports
sudo chown -R $USER:$USER /var/stasis

# Setup Python environment
echo "[4/6] Setting up Python environment..."
cd "$(dirname "$0")/../server"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Create default .env
echo "[5/6] Creating configuration..."
if [ ! -f .env ]; then
    cat > .env << EOF
STASIS_HOST=0.0.0.0
STASIS_PORT=5000
STASIS_DB=/var/stasis/stasis.db
STASIS_UART=/dev/ttyS0
STASIS_UART_BAUD=9600
STASIS_STATION_LAT=0.0
STASIS_STATION_LON=0.0
STASIS_CAM_URL=http://192.168.4.2:81/stream
STASIS_DEBUG=false
EOF
    echo "  Created .env — edit with your settings"
fi

# Create systemd service
echo "[6/6] Creating systemd service..."
SCRIPT_DIR="$(cd "$(dirname "$0")/../server" && pwd)"
sudo cat > /etc/systemd/system/stasis.service << EOF
[Unit]
Description=STASIS Forest Patrol Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=$SCRIPT_DIR/venv/bin/python3 app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable stasis

echo ""
echo "========================================"
echo "  Setup Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "  1. Edit server/.env with your settings"
echo "  2. Enable UART: sudo raspi-config → Serial"
echo "  3. Start: sudo systemctl start stasis"
echo "  4. Dashboard: http://$(hostname -I | awk '{print $1}'):5000"
echo ""

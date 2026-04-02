#!/bin/bash
# STASIS — Build Dashboard Script
# Builds the React dashboard and copies to server/public/

set -e

echo "========================================"
echo "  STASIS — Building Dashboard"
echo "========================================"

cd "$(dirname "$0")/../dashboard"

# Install dependencies
echo "[1/3] Installing dependencies..."
npm install

# Build
echo "[2/3] Building production bundle..."
npm run build

echo "[3/3] Done!"
echo ""
echo "Dashboard built to server/public/"
echo "Restart the server to serve the new build."

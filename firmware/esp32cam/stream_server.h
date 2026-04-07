#pragma once

// =====================================================================
// STASIS — MJPEG HTTP Stream Server (port 81)
// Endpoints: /stream (MJPEG), /capture (single JPEG), /status (JSON)
// Camera is in RGB565 mode for detection; frames are converted to
// JPEG on the fly via frame2jpg().
// =====================================================================

void startStreamServer();   // Call once after WiFi is connected
void handleStreamClients(); // Call every loop iteration
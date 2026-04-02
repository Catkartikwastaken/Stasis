#pragma once

// =====================================================================
// STASIS — ESP32-C3 Mini Configuration (Charging Station WiFi Bridge)
// =====================================================================

// ---- WiFi ----
#define WIFI_MODE_AP        1    // 1 = Access Point, 0 = Station
#define WIFI_AP_SSID        "STASIS_NET"
#define WIFI_AP_PASSWORD    "stasis2024"
#define WIFI_AP_CHANNEL     1
#define WIFI_AP_MAX_CONN    4

// Station mode (if WIFI_MODE_AP == 0)
#define WIFI_STA_SSID       ""
#define WIFI_STA_PASSWORD   ""

// ---- UART to Raspberry Pi ----
#define PI_UART_RX      20    // ESP32-C3 RX <- Pi TX (GPIO14/pin8)
#define PI_UART_TX      21    // ESP32-C3 TX -> Pi RX (GPIO15/pin10)
#define PI_UART_BAUD    9600

// ---- GPIO Control ----
#define CHARGING_RELAY_PIN  15   // HIGH = charging enabled
#define EMERGENCY_STOP_PIN  16   // Interrupt-driven signal to Pi

// ---- ESP-NOW ----
// ESP32-S3 Rover MAC address (update with actual)
#define ROVER_MAC {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF}

// ---- Watchdog ----
#define TELEMETRY_WATCHDOG_MS  60000  // Alert if no rover data for 60s

// ---- TCP Bridge ----
#define TCP_SERVER_PORT     80    // WiFi clients connect here
#define TCP_BUFFER_SIZE     2048

// ---- Firmware Info ----
#define C3_FIRMWARE_VERSION "1.0.0"

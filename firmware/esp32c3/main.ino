/*
 * STASIS — ESP32-C3 Mini Charging Station Bridge
 * WiFi AP + UART-TCP Bridge + ESP-NOW Relay
 * Version 1.0.0
 */

#include "config.h"
#include "wifi_bridge.h"
#include "uart_pi_bridge.h"
#include "espnow_relay.h"
#include "gpio_control.h"
#include <ArduinoJson.h>

WiFiBridge wifi;
UARTPiBridge piBridge;
ESPNowRelay espnow;
GPIOControl gpio;

// Watchdog
unsigned long lastRoverTelemetry = 0;
bool watchdogAlerted = false;

// Forward declarations
void onTelemetry(const uint8_t* data, size_t len);
void onAlert(const uint8_t* data, size_t len);
void processPiCommand(const String& json);

void setup() {
    Serial.begin(115200);
    Serial.println("\n=== STASIS Station v" C3_FIRMWARE_VERSION " ===");

    // GPIO
    gpio.begin();

    // WiFi
    if (wifi.begin()) {
        Serial.printf("[OK] WiFi %s: %s\n",
                      wifi.getMode().c_str(),
                      wifi.getIP().toString().c_str());
    }

    // ESP-NOW relay
    if (espnow.begin()) {
        Serial.println("[OK] ESP-NOW Relay");
    }
    espnow.setTelemetryCallback(onTelemetry);
    espnow.setAlertCallback(onAlert);

    // UART bridge to Pi
    piBridge.begin();
    Serial.println("[OK] Pi UART Bridge");

    Serial.println("=== Station Ready ===\n");
}

void loop() {
    // Update bridge
    piBridge.update();

    // Process Pi commands
    if (piBridge.hasPiData()) {
        String line = piBridge.readPiLine();
        line.trim();
        if (line.length() > 0 && line[0] == '{') {
            processPiCommand(line);
        }
    }

    // Watchdog: no rover telemetry for 60s
    if (espnow.isRoverConnected()) {
        watchdogAlerted = false;
    } else if (!watchdogAlerted && lastRoverTelemetry > 0) {
        watchdogAlerted = true;
        // Alert Pi
        StaticJsonDocument<128> doc;
        doc["type"] = "watchdog";
        doc["message"] = "No rover telemetry for 60s";
        doc["timestamp"] = millis();
        String json;
        serializeJson(doc, json);
        piBridge.sendToPi(json);
        Serial.println("[WATCHDOG] Rover telemetry timeout!");
    }

    yield();  // Prevent tight loop
}

// ---- ESP-NOW Callbacks ----
void onTelemetry(const uint8_t* data, size_t len) {
    lastRoverTelemetry = millis();

    // Forward raw telemetry as JSON to Pi
    if (len >= 2) {
        // Parse binary telemetry struct and convert to JSON
        struct __attribute__((packed)) {
            uint8_t  packet_type;
            float    gps_lat;
            float    gps_lon;
            float    temperature;
            float    battery_voltage;
            int16_t  accel_x, accel_y, accel_z;
            uint8_t  rover_state;
            uint8_t  is_charging;
        } telPkt;

        if (len >= sizeof(telPkt)) {
            memcpy(&telPkt, data, sizeof(telPkt));

            StaticJsonDocument<256> doc;
            doc["type"] = "telemetry";
            doc["lat"] = telPkt.gps_lat;
            doc["lon"] = telPkt.gps_lon;
            doc["temp"] = telPkt.temperature;
            doc["battery"] = telPkt.battery_voltage;
            doc["accel_x"] = telPkt.accel_x;
            doc["accel_y"] = telPkt.accel_y;
            doc["accel_z"] = telPkt.accel_z;
            doc["state"] = telPkt.rover_state;
            doc["charging"] = telPkt.is_charging;
            doc["timestamp"] = millis();

            String json;
            serializeJson(doc, json);
            piBridge.sendToPi(json);
        }
    }
}

void onAlert(const uint8_t* data, size_t len) {
    if (len < 2) return;

    uint8_t packetType = data[0];

    if (packetType == 0x03) {
        // Alert packet header
        struct __attribute__((packed)) {
            uint8_t  packet_type;
            uint8_t  alert_type;
            float    alert_lat;
            float    alert_lon;
            uint32_t timestamp;
        } alertHeader;

        if (len >= sizeof(alertHeader)) {
            memcpy(&alertHeader, data, sizeof(alertHeader));

            StaticJsonDocument<256> doc;
            doc["type"] = "alert";
            doc["alert_type"] = alertHeader.alert_type;
            doc["lat"] = alertHeader.alert_lat;
            doc["lon"] = alertHeader.alert_lon;
            doc["timestamp"] = alertHeader.timestamp;

            String json;
            serializeJson(doc, json);
            piBridge.sendToPi(json);
        }
    } else if (packetType == 0x04) {
        // Image chunk — forward as-is to Pi in hex-encoded form
        StaticJsonDocument<512> doc;
        doc["type"] = "image_chunk";
        doc["first"] = data[1];
        doc["last"] = data[2];

        // Base64 chunk data
        String chunk = "";
        for (size_t i = 3; i < len; i++) {
            chunk += (char)data[i];
        }
        doc["data"] = chunk;

        String json;
        serializeJson(doc, json);
        piBridge.sendToPi(json);
    }
}

// ---- Process Pi Commands ----
void processPiCommand(const String& json) {
    StaticJsonDocument<512> doc;
    DeserializationError err = deserializeJson(doc, json);
    if (err) return;

    const char* type = doc["type"] | "";

    if (strcmp(type, "command") == 0) {
        // Forward command to rover via ESP-NOW
        uint8_t cmdBuf[256];
        size_t cmdLen = 0;

        uint8_t command = doc["command"] | 0;

        // Build CommandPacket
        struct __attribute__((packed)) {
            uint8_t  packet_type;
            uint8_t  command;
            float    target_lat;
            float    target_lon;
            uint8_t  geofence_point_count;
            float    geofence_lats[10];
            float    geofence_lons[10];
        } cmdPkt;

        cmdPkt.packet_type = 0x02;
        cmdPkt.command = command;
        cmdPkt.target_lat = doc["target_lat"] | 0.0f;
        cmdPkt.target_lon = doc["target_lon"] | 0.0f;

        JsonArray lats = doc["geofence_lats"];
        JsonArray lons = doc["geofence_lons"];
        cmdPkt.geofence_point_count = min((size_t)lats.size(), (size_t)10);
        for (uint8_t i = 0; i < cmdPkt.geofence_point_count; i++) {
            cmdPkt.geofence_lats[i] = lats[i];
            cmdPkt.geofence_lons[i] = lons[i];
        }

        espnow.sendCommandToRover((uint8_t*)&cmdPkt, sizeof(cmdPkt));
        Serial.printf("[CMD] Forwarded command %d to rover\n", command);

    } else if (strcmp(type, "charging") == 0) {
        bool enable = doc["enable"] | false;
        gpio.setChargingRelay(enable);

    } else if (strcmp(type, "emergency") == 0) {
        gpio.triggerEmergencyStop();
    }
}

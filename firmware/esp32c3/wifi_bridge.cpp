#include "wifi_bridge.h"
#include "config.h"

bool WiFiBridge::begin() {
    _apMode = WIFI_MODE_AP;

    if (_apMode) {
        return setupAP();
    } else {
        return setupSTA();
    }
}

bool WiFiBridge::setupAP() {
    WiFi.mode(WIFI_AP_STA);  // AP + STA for ESP-NOW compatibility
    WiFi.softAP(WIFI_AP_SSID, WIFI_AP_PASSWORD, WIFI_AP_CHANNEL, 0, WIFI_AP_MAX_CONN);

    IPAddress ip = WiFi.softAPIP();
    Serial.printf("[WIFI] AP started: %s @ %s\n", WIFI_AP_SSID, ip.toString().c_str());
    return true;
}

bool WiFiBridge::setupSTA() {
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_STA_SSID, WIFI_STA_PASSWORD);

    unsigned long start = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - start < 15000) {
        delay(500);
        Serial.print(".");
    }
    Serial.println();

    if (WiFi.status() == WL_CONNECTED) {
        Serial.printf("[WIFI] STA connected: %s\n", WiFi.localIP().toString().c_str());
        return true;
    }

    Serial.println("[WIFI] STA connection failed, falling back to AP");
    return setupAP();
}

bool WiFiBridge::isConnected() const {
    if (_apMode) return true;
    return WiFi.status() == WL_CONNECTED;
}

IPAddress WiFiBridge::getIP() const {
    if (_apMode) return WiFi.softAPIP();
    return WiFi.localIP();
}

String WiFiBridge::getMode() const {
    return _apMode ? "AP" : "STA";
}

uint8_t WiFiBridge::getClientCount() const {
    if (_apMode) return WiFi.softAPgetStationNum();
    return 0;
}

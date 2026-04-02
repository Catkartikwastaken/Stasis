#include "espnow_relay.h"
#include "config.h"
#include <WiFi.h>

ESPNowRelay* ESPNowRelay::_instance = nullptr;
TelemetryCallback ESPNowRelay::_telemetryCb = nullptr;
AlertCallback ESPNowRelay::_alertCb = nullptr;

bool ESPNowRelay::begin() {
    _instance = this;

    if (esp_now_init() != ESP_OK) {
        Serial.println("[ESPNOW] Init failed");
        return false;
    }

    esp_now_register_recv_cb(onDataRecv);
    esp_now_register_send_cb(onDataSent);

    // Add rover as peer
    esp_now_peer_info_t peerInfo = {};
    uint8_t roverMac[] = ROVER_MAC;
    memcpy(peerInfo.peer_addr, roverMac, 6);
    peerInfo.channel = 0;
    peerInfo.encrypt = false;

    if (esp_now_add_peer(&peerInfo) != ESP_OK) {
        Serial.println("[ESPNOW] Add rover peer failed");
        return false;
    }

    Serial.println("[ESPNOW] Relay initialized");
    return true;
}

void ESPNowRelay::sendCommandToRover(const uint8_t* data, size_t len) {
    uint8_t roverMac[] = ROVER_MAC;
    esp_err_t result = esp_now_send(roverMac, data, len);
    if (result != ESP_OK) {
        Serial.println("[ESPNOW] Command send failed");
    }
}

void ESPNowRelay::setTelemetryCallback(TelemetryCallback cb) {
    _telemetryCb = cb;
}

void ESPNowRelay::setAlertCallback(AlertCallback cb) {
    _alertCb = cb;
}

bool ESPNowRelay::isRoverConnected() const {
    return (millis() - _lastRx) < TELEMETRY_WATCHDOG_MS;
}

void ESPNowRelay::onDataSent(const uint8_t* mac, esp_now_send_status_t status) {
    if (_instance) {
        _instance->_sendOk = (status == ESP_NOW_SEND_SUCCESS);
    }
}

void ESPNowRelay::onDataRecv(const uint8_t* mac, const uint8_t* data, int len) {
    if (!_instance || len < 1) return;

    _instance->_lastRx = millis();

    uint8_t packetType = data[0];

    switch (packetType) {
        case 0x01:  // Telemetry
            if (_telemetryCb) _telemetryCb(data, len);
            break;

        case 0x03:  // Alert
            if (_alertCb) _alertCb(data, len);
            break;

        case 0x04:  // Image chunk (part of alert)
            if (_alertCb) _alertCb(data, len);
            break;

        default:
            Serial.printf("[ESPNOW] Unknown packet type: 0x%02X\n", packetType);
            break;
    }
}

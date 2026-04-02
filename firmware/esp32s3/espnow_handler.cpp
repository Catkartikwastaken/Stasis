#include "espnow_handler.h"
#include <WiFi.h>
#include <esp_now.h>

ESPNowHandler* ESPNowHandler::_instance = nullptr;
CommandCallback ESPNowHandler::_cmdCallback = nullptr;

bool ESPNowHandler::begin() {
    _instance = this;

    WiFi.mode(WIFI_STA);
    WiFi.disconnect();

    if (esp_now_init() != ESP_OK) {
        Serial.println("[ESPNOW] Init failed");
        return false;
    }

    esp_now_register_send_cb(onDataSent);
    esp_now_register_recv_cb(onDataRecv);

    // Add station peer
    esp_now_peer_info_t peerInfo = {};
    uint8_t stationMac[] = STATION_MAC;
    memcpy(peerInfo.peer_addr, stationMac, 6);
    peerInfo.channel = 0;
    peerInfo.encrypt = false;

    if (esp_now_add_peer(&peerInfo) != ESP_OK) {
        Serial.println("[ESPNOW] Add peer failed");
        return false;
    }

    _connected = true;
    Serial.println("[ESPNOW] Initialized");
    return true;
}

void ESPNowHandler::sendTelemetry(const TelemetryPacket& pkt) {
    uint8_t stationMac[] = STATION_MAC;
    esp_now_send(stationMac, (uint8_t*)&pkt, sizeof(TelemetryPacket));
}

void ESPNowHandler::sendAlert(const AlertPacket& pkt) {
    uint8_t stationMac[] = STATION_MAC;
    // For large alerts (with image), may need to chunk
    // Send header first (without image)
    size_t headerSize = offsetof(AlertPacket, image_b64);
    esp_now_send(stationMac, (uint8_t*)&pkt, headerSize);

    // Send image chunks if present
    if (pkt.alert_type == ALERT_HUMAN && strlen(pkt.image_b64) > 0) {
        const size_t chunkSize = 240;  // ESP-NOW max payload ~250 bytes
        size_t imgLen = strlen(pkt.image_b64);
        for (size_t offset = 0; offset < imgLen; offset += chunkSize) {
            size_t len = min(chunkSize, imgLen - offset);
            uint8_t chunk[244];
            chunk[0] = 0x04;  // Image chunk marker
            chunk[1] = (offset == 0) ? 0x01 : 0x00;  // First chunk flag
            chunk[2] = (offset + len >= imgLen) ? 0x01 : 0x00;  // Last chunk flag
            memcpy(chunk + 3, pkt.image_b64 + offset, len);
            esp_now_send(stationMac, chunk, len + 3);
            delay(5);  // Throttle
        }
    }
}

void ESPNowHandler::setCommandCallback(CommandCallback cb) {
    _cmdCallback = cb;
}

void ESPNowHandler::onDataSent(const uint8_t* mac, esp_now_send_status_t status) {
    if (_instance) {
        _instance->_connected = (status == ESP_NOW_SEND_SUCCESS);
    }
}

void ESPNowHandler::onDataRecv(const uint8_t* mac, const uint8_t* data, int len) {
    if (!_instance || len < 1) return;

    _instance->_lastRxTime = millis();

    if (data[0] == PKT_COMMAND && len >= (int)sizeof(CommandPacket)) {
        CommandPacket cmd;
        memcpy(&cmd, data, sizeof(CommandPacket));
        if (_cmdCallback) {
            _cmdCallback(cmd);
        }
    }
}

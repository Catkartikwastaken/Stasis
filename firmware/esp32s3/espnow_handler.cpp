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
    // Send the alert header (fits within ESP-NOW 250-byte limit)
    esp_now_send(stationMac, (uint8_t*)&pkt, sizeof(AlertPacket));
}

void ESPNowHandler::sendImageChunked(const char* base64Data, size_t dataLen) {
    uint8_t stationMac[] = STATION_MAC;
    const size_t chunkDataSize = IMAGE_CHUNK_DATA_SIZE;

    for (size_t offset = 0; offset < dataLen; offset += chunkDataSize) {
        ImageChunkPacket chunk = {};
        chunk.packet_type = PKT_IMAGE_CHUNK;
        chunk.is_first = (offset == 0) ? 1 : 0;
        size_t len = min(chunkDataSize, dataLen - offset);
        chunk.is_last = (offset + len >= dataLen) ? 1 : 0;
        memcpy(chunk.data, base64Data + offset, len);

        // Header (3 bytes) + data
        esp_now_send(stationMac, (uint8_t*)&chunk, 3 + len);

        // Yield to avoid watchdog — use millis() based throttle
        unsigned long t = millis();
        while (millis() - t < 5) { yield(); }
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

#include "camera_comms.h"
#include "config.h"
#include <ArduinoJson.h>

void CameraComms::begin() {
    Serial1.begin(CAM_BAUD, SERIAL_8N1, CAM_RX_PIN, CAM_TX_PIN);
    _rxBuffer.reserve(6144);
    _newDetection = false;
    memset(&_detection, 0, sizeof(_detection));
}

void CameraComms::update() {
    while (Serial1.available()) {
        char c = Serial1.read();
        if (c == '\n') {
            _rxBuffer.trim();
            if (_rxBuffer.length() > 0 && _rxBuffer[0] == '{') {
                // Check cooldown
                if (millis() - _lastCooldown >= DETECTION_COOLDOWN_MS) {
                    parsePayload(_rxBuffer);
                }
            }
            _rxBuffer = "";
        } else if (c != '\r') {
            if (_rxBuffer.length() < 6000) {
                _rxBuffer += c;
            }
        }
    }
}

void CameraComms::parsePayload(const String& json) {
    StaticJsonDocument<5120> doc;
    DeserializationError err = deserializeJson(doc, json);
    if (err) return;

    const char* event = doc["event"] | "";
    if (strcmp(event, "human_detected") == 0) {
        _detection.detected = true;
        _detection.confidence = doc["confidence"] | 0.0f;
        _detection.timestamp = doc["timestamp"] | (uint32_t)millis();

        const char* img = doc["image"] | "";
        strncpy(_detection.image_b64, img, sizeof(_detection.image_b64) - 1);
        _detection.image_b64[sizeof(_detection.image_b64) - 1] = '\0';

        _newDetection = true;
        _lastCooldown = millis();
    }
}

CameraDetection CameraComms::getDetection() {
    CameraDetection det = _detection;
    return det;
}

void CameraComms::clearDetection() {
    _newDetection = false;
    _detection.detected = false;
}

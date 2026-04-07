#include "uart_comms.h"
#include "config.h"
#include "mbedtls/base64.h"   // Bundled in ESP32 Arduino Core — no install needed

void UARTComms::init() {
    Serial.begin(UART_BAUD);
}

void UARTComms::sendBase64Chunked(const uint8_t* buf, size_t len) {
    // Encode in 48-byte chunks (48 raw → 64 base64 chars, no padding issues)
    const size_t CHUNK_RAW = 48;
    unsigned char out[65];   // 64 base64 chars + NUL
    size_t olen = 0;

    for (size_t i = 0; i < len; i += CHUNK_RAW) {
        size_t chunk = len - i;
        if (chunk > CHUNK_RAW) chunk = CHUNK_RAW;

        mbedtls_base64_encode(out, sizeof(out), &olen, buf + i, chunk);
        out[olen] = '\0';
        Serial.print((const char*)out);
    }
}

void UARTComms::sendAlert(float confidence, const uint8_t* jpgBuf, size_t jpgLen) {
    if (!jpgBuf || jpgLen == 0) {
        sendLog("alert_no_image");
        return;
    }

    // STASIS spec JSON format
    Serial.print("{\"event\":\"human_detected\",\"confidence\":");
    Serial.print(confidence, 2);
    Serial.print(",\"timestamp\":");
    Serial.print(millis());
    Serial.print(",\"image\":\"");

    sendBase64Chunked(jpgBuf, jpgLen);

    Serial.println("\"}");
}

void UARTComms::sendLog(const char* msg) {
    Serial.print("{\"log\":\"");
    Serial.print(msg);
    Serial.println("\"}");
}
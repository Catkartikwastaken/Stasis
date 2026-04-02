#include "uart_comms.h"
#include "config.h"
#include "base64.h"

void UARTComms::init() {
    Serial.begin(UART_BAUD);
}

void UARTComms::encodeAndSendBase64Chunked(uint8_t* buf, size_t len) {
    // Base64 chunking to prevent memory allocation crashes
    const int CHUNK_SIZE = 45; // multiple of 3
    for (size_t i = 0; i < len; i += CHUNK_SIZE) {
        size_t chunk_len = min((size_t)CHUNK_SIZE, len - i);
        String b64 = base64::encode(buf + i, chunk_len);
        Serial.print(b64);
    }
}

void UARTComms::sendAlert(float confidence, camera_fb_t* fb) {
    uint8_t *jpg_buf = NULL;
    size_t jpg_len = 0;

    // Convert RGB565 to JPEG in memory for the snapshot requirement
    if (!fmt2jpg(fb->buf, fb->len, fb->width, fb->height, fb->format, 30, &jpg_buf, &jpg_len)) {
        sendLog("jpeg_compression_failed");
        return;
    }

    // STASIS Spec JSON format
    Serial.print("{\"event\":\"human_detected\",\"confidence\":");
    Serial.print(confidence, 2);
    Serial.print(",\"timestamp\":");
    Serial.print(millis());
    Serial.print(",\"image\":\"");
    
    encodeAndSendBase64Chunked(jpg_buf, jpg_len);
    
    Serial.println("\"}");

    free(jpg_buf);
}

void UARTComms::sendLog(const char* msg) {
    Serial.print("{\"log\":\"");
    Serial.print(msg);
    Serial.println("\"}");
}
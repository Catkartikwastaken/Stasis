#pragma once

// =====================================================================
// STASIS — UART Communication to ESP32-S3
// Sends JSON messages over Serial (GPIO1/3) at UART_BAUD.
//
// Arduino IDE: No external libraries needed.
//   Uses mbedtls (bundled in ESP32 Arduino Core) for Base64 encoding.
// =====================================================================

#include <Arduino.h>

class UARTComms {
public:
    static void init();

    // Send a human-detected alert with JPEG snapshot
    // jpgBuf/jpgLen: pre-captured JPEG (from HumanDetector::captureJPEG)
    static void sendAlert(float confidence, const uint8_t* jpgBuf, size_t jpgLen);

    // Send a JSON log message
    static void sendLog(const char* msg);

private:
    // Stream Base64 in chunks to avoid large heap allocation
    static void sendBase64Chunked(const uint8_t* buf, size_t len);
};
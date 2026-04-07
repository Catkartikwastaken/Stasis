// =====================================================================
// STASIS — ESP32-CAM Main Firmware
//
// Arduino IDE Setup:
//   Board:     "AI Thinker ESP32-CAM"
//   Partition: "Huge APP (3MB No OTA / 1MB SPIFFS)"
//   PSRAM:     "Enabled"
//   Core:      ESP32 Arduino Core 2.0.x
//
// Pipeline:
//   Motion detect → Buzzer → ESP-WHO face detect → UART alert
// =====================================================================

#include <esp_camera.h>
#include <WiFi.h>
#include "config.h"
#include "human_detector.h"
#include "stream_server.h"
#include "uart_comms.h"

HumanDetector detector;

void setup() {
    UARTComms::init();
    pinMode(BUZZER_PIN, OUTPUT);
    digitalWrite(BUZZER_PIN, LOW);
    pinMode(FLASH_LED_PIN, OUTPUT);
    digitalWrite(FLASH_LED_PIN, LOW);

    // ---- Camera Init ----
    camera_config_t config;
    config.ledc_channel = LEDC_CHANNEL_0;
    config.ledc_timer   = LEDC_TIMER_0;
    config.pin_d0       = Y2_GPIO_NUM;
    config.pin_d1       = Y3_GPIO_NUM;
    config.pin_d2       = Y4_GPIO_NUM;
    config.pin_d3       = Y5_GPIO_NUM;
    config.pin_d4       = Y6_GPIO_NUM;
    config.pin_d5       = Y7_GPIO_NUM;
    config.pin_d6       = Y8_GPIO_NUM;
    config.pin_d7       = Y9_GPIO_NUM;
    config.pin_xclk     = XCLK_GPIO_NUM;
    config.pin_pclk     = PCLK_GPIO_NUM;
    config.pin_vsync    = VSYNC_GPIO_NUM;
    config.pin_href     = HREF_GPIO_NUM;
    config.pin_sscb_sda = SIOD_GPIO_NUM;
    config.pin_sscb_scl = SIOC_GPIO_NUM;
    config.pin_pwdn     = PWDN_GPIO_NUM;
    config.pin_reset    = RESET_GPIO_NUM;
    config.xclk_freq_hz = 20000000;

    // RGB565 required for motion detection and ESP-WHO face detect
    config.pixel_format = PIXFORMAT_RGB565;
    config.frame_size   = FRAMESIZE_QVGA;    // 320×240
    config.fb_count     = 1;                  // Save PSRAM for MTMN

    esp_err_t err = esp_camera_init(&config);
    if (err != ESP_OK) {
        UARTComms::sendLog("camera_fail");
        return;
    }

    // ---- Detection Pipeline Init ----
    if (!detector.init()) {
        UARTComms::sendLog("detector_init_fail");
        return;
    }

    // ---- WiFi for MJPEG streaming ----
    WiFi.mode(WIFI_STA);
    WiFi.begin(CAM_WIFI_SSID, CAM_WIFI_PASS);
    unsigned long wifiStart = millis();
    while (WiFi.status() != WL_CONNECTED) {
        if (millis() - wifiStart > CAM_WIFI_TIMEOUT) {
            UARTComms::sendLog("wifi_timeout");
            break;
        }
        yield();   // Let watchdog breathe — no delay()
    }

    if (WiFi.status() == WL_CONNECTED) {
        startStreamServer();
        char ipMsg[48];
        snprintf(ipMsg, sizeof(ipMsg), "STREAM_IP:%s", WiFi.localIP().toString().c_str());
        UARTComms::sendLog(ipMsg);
    }

    UARTComms::sendLog("STASIS_CAM_ONLINE");
}

void loop() {
    // Run detection state machine (motion → buzzer → face detect → alert)
    detector.update();

    // Service HTTP stream clients (non-blocking)
    handleStreamClients();

    // Check if the detector has a confirmed human alert
    if (detector.hasAlert()) {
        DetectionResult result = detector.getResult();

        // Capture a JPEG snapshot for the alert
        uint8_t* jpgBuf = nullptr;
        size_t   jpgLen = 0;
        if (detector.captureJPEG(&jpgBuf, &jpgLen)) {
            UARTComms::sendAlert(result.confidence, jpgBuf, jpgLen);
            free(jpgBuf);
        } else {
            // Send alert without image if capture fails
            UARTComms::sendAlert(result.confidence, nullptr, 0);
        }
    }
}
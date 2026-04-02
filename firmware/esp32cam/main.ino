#include "esp_camera.h"
#include "config.h"
#include "human_detector.h"
#include "uart_comms.h"

HumanDetector detector;

void setup() {
    UARTComms::init();
    pinMode(BUZZER_PIN, OUTPUT);
    digitalWrite(BUZZER_PIN, LOW);

    camera_config_t config;
    config.ledc_channel = LEDC_CHANNEL_0;
    config.ledc_timer = LEDC_TIMER_0;
    config.pin_d0 = Y2_GPIO_NUM;
    config.pin_d1 = Y3_GPIO_NUM;
    config.pin_d2 = Y4_GPIO_NUM;
    config.pin_d3 = Y5_GPIO_NUM;
    config.pin_d4 = Y6_GPIO_NUM;
    config.pin_d5 = Y7_GPIO_NUM;
    config.pin_d6 = Y8_GPIO_NUM;
    config.pin_d7 = Y9_GPIO_NUM;
    config.pin_xclk = XCLK_GPIO_NUM;
    config.pin_pclk = PCLK_GPIO_NUM;
    config.pin_vsync = VSYNC_GPIO_NUM;
    config.pin_href = HREF_GPIO_NUM;
    config.pin_sscb_sda = SIOD_GPIO_NUM;
    config.pin_sscb_scl = SIOC_GPIO_NUM;
    config.pin_pwdn = PWDN_GPIO_NUM;
    config.pin_reset = RESET_GPIO_NUM;
    config.xclk_freq_hz = 20000000;
    
    // RGB565 required for ESP-WHO stage 2 classification
    config.pixel_format = PIXFORMAT_RGB565; 
    config.frame_size = FRAMESIZE_QVGA; 
    config.fb_count = 1;

    esp_err_t err = esp_camera_init(&config);
    if (err != ESP_OK) {
        UARTComms::sendLog("camera_fail");
        return;
    }

    if (!detector.init()) {
        UARTComms::sendLog("mem_fail");
        return;
    }

    UARTComms::sendLog("STASIS_CAM_ONLINE");
}

void loop() {
    detector.update();

    if (detector.hasPendingAlert()) {
        UARTComms::sendAlert(detector.getLastConfidence(), detector.getLastFrame());
        esp_camera_fb_return(detector.getLastFrame()); // Free frame after UART TX
    }
}
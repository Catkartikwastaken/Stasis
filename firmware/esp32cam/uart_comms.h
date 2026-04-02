#pragma once
#include "Arduino.h"
#include "esp_camera.h"

class UARTComms {
public:
    static void init();
    static void sendAlert(float confidence, camera_fb_t* fb);
    static void sendLog(const char* msg);

private:
    static void encodeAndSendBase64Chunked(uint8_t* buf, size_t len);
};
#pragma once
#include <Arduino.h>

struct CameraDetection {
    bool    detected;
    float   confidence;
    uint32_t timestamp;
    char    image_b64[4096];
};

class CameraComms {
public:
    void begin();
    void update();
    bool hasNewDetection() const { return _newDetection; }
    CameraDetection getDetection();
    void clearDetection();

private:
    String _rxBuffer;
    bool _newDetection = false;
    CameraDetection _detection;
    unsigned long _lastCooldown = 0;
    void parsePayload(const String& json);
};

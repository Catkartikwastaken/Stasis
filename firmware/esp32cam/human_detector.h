#pragma once
#include "esp_camera.h"
#include "fd_forward.h"

enum DetectorState {
    STATE_IDLE,
    STATE_TRACKING,
    STATE_DETECTING,
    STATE_COOLDOWN
};

class HumanDetector {
public:
    HumanDetector();
    bool init();
    void update();
    DetectorState getState() { return _state; }
    bool hasPendingAlert();
    camera_fb_t* getLastFrame() { return _last_alert_fb; }
    float getLastConfidence() { return _last_confidence; }

private:
    DetectorState _state;
    uint8_t* _prev_frame;
    unsigned long _state_timer;
    unsigned long _cooldown_timer;
    bool _alert_ready;
    float _last_confidence;
    camera_fb_t* _last_alert_fb;

    bool checkMotion(camera_fb_t* fb);
    bool runInference(camera_fb_t* fb);
    void setBuzzer(bool on);
};
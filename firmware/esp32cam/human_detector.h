#pragma once

// =====================================================================
// STASIS — Human Detection Module
// Pipeline: Motion Detect → Buzzer → ESP-WHO Face Detect → Alert
//
// Arduino IDE requirements:
//   Board: "AI Thinker ESP32-CAM"
//   ESP32 Arduino Core 2.0.x (has fd_forward.h bundled)
//   PSRAM: Enabled (MTMN face detection needs PSRAM)
// =====================================================================

#include <esp_camera.h>

// ESP-WHO / esp-face detection headers (bundled in ESP32 Arduino Core 2.0.x)
#include "fd_forward.h"          // face_detect(), mtmn_config_t, box_array_t
#include "dl_lib_matrix3d.h"     // dl_matrix3du_t, dl_matrix3du_alloc/free

// Detection state machine
// Flow: IDLE → MOTION_DETECTED → BUZZER_ON → FACE_DETECT → ALERT_READY → COOLDOWN → IDLE
enum DetectState : uint8_t {
    DET_IDLE           = 0,   // Watching for motion (frame differencing)
    DET_MOTION_FOUND   = 1,   // Motion confirmed, prepare for face detect
    DET_BUZZER_ON      = 2,   // Buzzer sounding to warn
    DET_FACE_DETECT    = 3,   // Running ESP-WHO MTMN face detection
    DET_ALERT_READY    = 4,   // Human confirmed — alert pending pickup by main loop
    DET_COOLDOWN       = 5    // Post-alert cooldown (30s)
};

// Result of a confirmed detection
struct DetectionResult {
    float    confidence;       // MTMN face score
    uint32_t timestamp;        // millis() at detection time
    bool     ready;            // True if result is pending
};

class HumanDetector {
public:
    bool init();
    void update();              // Call every loop iteration

    DetectState getState() const { return _state; }
    bool hasAlert() const { return _result.ready; }
    DetectionResult getResult();  // Reads and clears the result

    // Capture a JPEG snapshot of the current frame (for sending via UART)
    // Caller must free() the returned buffer
    bool captureJPEG(uint8_t** outBuf, size_t* outLen);

private:
    DetectState _state = DET_IDLE;
    DetectionResult _result = {0, 0, false};

    // Motion detection
    uint8_t* _prevGray = nullptr;        // Previous frame grayscale buffer
    uint32_t _prevGrayLen = 0;
    bool _prevFrameValid = false;

    // Timing
    unsigned long _stateEnteredAt = 0;
    unsigned long _cooldownStart = 0;

    // ESP-WHO face detection config (MTMN)
    mtmn_config_t _mtmnConfig;

    // Internal pipeline stages
    void enterState(DetectState newState);
    bool detectMotion(camera_fb_t* fb);
    bool detectFace(camera_fb_t* fb, float* outConfidence);
    void buzzerOn();
    void buzzerOff();
};
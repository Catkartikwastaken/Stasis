#include "human_detector.h"
#include "config.h"
#include <Arduino.h>

// =====================================================================
// STASIS — Human Detection Implementation
//
// Pipeline per STASIS spec:
//   1. Frame differencing detects motion (no ESP-WHO needed)
//   2. Buzzer activates to warn
//   3. ESP-WHO MTMN face detection confirms human presence
//   4. If confidence >= ALERT_CONFIDENCE → fire alert
//   5. 30-second cooldown
//
// ESP-WHO integration:
//   Uses esp-face library bundled in ESP32 Arduino Core 2.0.x.
//   - fd_forward.h  → face_detect(), mtmn_config_t
//   - dl_lib_matrix3d.h → dl_matrix3du_t matrix operations
//   The MTMN (Multi-Task Cascaded Neural Network) model runs on
//   the ESP32's dual cores with PSRAM for intermediate buffers.
// =====================================================================

// ---------- Initialization ----------

bool HumanDetector::init() {
    // Allocate grayscale buffer for motion detection (QVGA = 320×240)
    // We sample every MOTION_SAMPLE_STEP pixel, so buffer is smaller
    _prevGrayLen = (320 * 240) / MOTION_SAMPLE_STEP;
    _prevGray = (uint8_t*)ps_malloc(_prevGrayLen);  // Use PSRAM
    if (!_prevGray) {
        // Fallback to regular heap
        _prevGray = (uint8_t*)malloc(_prevGrayLen);
    }
    if (!_prevGray) {
        Serial.println("[DET] Failed to allocate motion buffer");
        return false;
    }
    memset(_prevGray, 0, _prevGrayLen);
    _prevFrameValid = false;

    // Configure MTMN face detection network
    // These settings balance speed vs. detection range on ESP32-CAM
    _mtmnConfig.type = FAST;                         // FAST mode (vs NORMAL)
    _mtmnConfig.min_face = (int)(FACE_MIN_SIZE * 240); // Min face pixels
    _mtmnConfig.pyramid = 0.707f;                    // Image pyramid scale
    _mtmnConfig.pyramid_times = 4;                   // Pyramid levels
    _mtmnConfig.p_threshold.score = FACE_SCORE_THRESHOLD;
    _mtmnConfig.p_threshold.nms = 0.7f;              // Non-max suppression
    _mtmnConfig.p_threshold.candidate_number = 20;
    _mtmnConfig.r_threshold.score = 0.7f;
    _mtmnConfig.r_threshold.nms = 0.7f;
    _mtmnConfig.r_threshold.candidate_number = 10;
    _mtmnConfig.o_threshold.score = 0.7f;
    _mtmnConfig.o_threshold.nms = 0.7f;
    _mtmnConfig.o_threshold.candidate_number = 1;

    // Buzzer pin
    pinMode(BUZZER_PIN, OUTPUT);
    digitalWrite(BUZZER_PIN, LOW);

    _state = DET_IDLE;
    Serial.println("[DET] Human detector initialized (ESP-WHO MTMN)");
    return true;
}

// ---------- Buzzer ----------

void HumanDetector::buzzerOn() {
    digitalWrite(BUZZER_PIN, HIGH);
}

void HumanDetector::buzzerOff() {
    digitalWrite(BUZZER_PIN, LOW);
}

// ---------- State Transitions ----------

void HumanDetector::enterState(DetectState newState) {
    // Cleanup on exit from old state
    if (_state == DET_BUZZER_ON) {
        buzzerOff();
    }

    _state = newState;
    _stateEnteredAt = millis();

#ifdef DEBUG_MODE
    static const char* stateNames[] = {
        "IDLE", "MOTION_FOUND", "BUZZER_ON", "FACE_DETECT", "ALERT_READY", "COOLDOWN"
    };
    Serial.printf("[DET] State → %s\n", stateNames[newState]);
#endif
}

// ---------- Stage 1: Motion Detection (Frame Differencing) ----------
// No ESP-WHO needed here — pure pixel math on grayscale samples.

bool HumanDetector::detectMotion(camera_fb_t* fb) {
    if (!fb || !_prevGray) return false;
    if (fb->format != PIXFORMAT_RGB565) return false;

    uint16_t* pixels = (uint16_t*)fb->buf;
    uint32_t totalPixels = fb->width * fb->height;
    uint32_t sampleCount = 0;
    uint32_t changedCount = 0;

    for (uint32_t i = 0; i < totalPixels && sampleCount < _prevGrayLen; i += MOTION_SAMPLE_STEP) {
        // Extract luminance from RGB565: use green channel (6 bits, best SNR)
        // RGB565: RRRRRGGG GGGBBBBB
        uint16_t px = pixels[i];
        uint8_t green = (uint8_t)((px >> 3) & 0xFC);  // 6-bit green → 8-bit

        if (_prevFrameValid) {
            int delta = abs((int)green - (int)_prevGray[sampleCount]);
            if (delta > MOTION_PIXEL_THRESHOLD) {
                changedCount++;
            }
        }
        _prevGray[sampleCount] = green;
        sampleCount++;
    }

    _prevFrameValid = true;

    if (sampleCount == 0) return false;
    float ratio = (float)changedCount / (float)sampleCount;
    return ratio > MOTION_PIXEL_RATIO;
}

// ---------- Stage 2: ESP-WHO Face Detection (MTMN) ----------
// This is where esp-face/ESP-WHO is used.
// Converts frame to RGB888, runs MTMN neural network.

bool HumanDetector::detectFace(camera_fb_t* fb, float* outConfidence) {
    if (!fb) return false;

    // Allocate RGB888 matrix in PSRAM for MTMN input
    dl_matrix3du_t* image = dl_matrix3du_alloc(1, fb->width, fb->height, 3);
    if (!image) {
        Serial.println("[DET] MTMN matrix alloc failed (need PSRAM!)");
        return false;
    }

    // Convert RGB565 → RGB888 (required by MTMN)
    if (!fmt2rgb888(fb->buf, fb->len, fb->format, image->item)) {
        Serial.println("[DET] RGB conversion failed");
        dl_matrix3du_free(image);
        return false;
    }

    // Run MTMN face detection
    box_array_t* faces = face_detect(image, &_mtmnConfig);

    bool detected = false;
    if (faces && faces->len > 0) {
        // Take the highest-confidence face
        float bestScore = 0;
        for (int i = 0; i < faces->len; i++) {
            if (faces->score[i] > bestScore) {
                bestScore = faces->score[i];
            }
        }

        if (bestScore >= ALERT_CONFIDENCE) {
            detected = true;
            *outConfidence = bestScore;
        }

#ifdef DEBUG_MODE
        Serial.printf("[DET] MTMN found %d face(s), best=%.2f %s\n",
                      faces->len, bestScore,
                      detected ? "→ ALERT" : "→ below threshold");
#endif

        // Free MTMN result memory
        dl_lib_free(faces->score);
        dl_lib_free(faces->box);
        dl_lib_free(faces->landmark);
        free(faces);
    }

    dl_matrix3du_free(image);
    return detected;
}

// ---------- Capture JPEG Snapshot ----------
// Grabs a fresh frame, converts to JPEG.
// Caller is responsible for free()ing the output buffer.

bool HumanDetector::captureJPEG(uint8_t** outBuf, size_t* outLen) {
    *outBuf = nullptr;
    *outLen = 0;

    camera_fb_t* fb = esp_camera_fb_get();
    if (!fb) return false;

    bool ok = false;
    if (fb->format == PIXFORMAT_JPEG) {
        // Already JPEG — copy the buffer
        *outBuf = (uint8_t*)malloc(fb->len);
        if (*outBuf) {
            memcpy(*outBuf, fb->buf, fb->len);
            *outLen = fb->len;
            ok = true;
        }
    } else {
        // Convert RGB565 → JPEG
        ok = frame2jpg(fb, 80, outBuf, outLen);
    }

    esp_camera_fb_return(fb);
    return ok;
}

// ---------- Get Result ----------

DetectionResult HumanDetector::getResult() {
    DetectionResult r = _result;
    _result.ready = false;
    return r;
}

// ---------- Main Update (called every loop) ----------

void HumanDetector::update() {
    unsigned long now = millis();

    // ---- COOLDOWN: wait 30 seconds after last alert ----
    if (_state == DET_COOLDOWN) {
        if (now - _cooldownStart >= DETECT_COOLDOWN_MS) {
            enterState(DET_IDLE);
        }
        return;
    }

    // ---- ALERT_READY: waiting for main loop to pick up result ----
    if (_state == DET_ALERT_READY) {
        // Stay in this state until main loop calls getResult()
        if (!_result.ready) {
            _cooldownStart = now;
            enterState(DET_COOLDOWN);
        }
        return;
    }

    // ---- Grab a frame ----
    camera_fb_t* fb = esp_camera_fb_get();
    if (!fb) return;

    switch (_state) {
        case DET_IDLE: {
            // Stage 1: Check for motion (no ESP-WHO here)
            if (detectMotion(fb)) {
                enterState(DET_MOTION_FOUND);
            }
            break;
        }

        case DET_MOTION_FOUND: {
            // Motion confirmed → activate buzzer, brief settle time
            buzzerOn();
            enterState(DET_BUZZER_ON);
            break;
        }

        case DET_BUZZER_ON: {
            // Buzzer sounds for BUZZER_DURATION_MS, then move to face detect
            if (now - _stateEnteredAt >= BUZZER_DURATION_MS) {
                buzzerOff();
                enterState(DET_FACE_DETECT);
            }
            // Keep updating motion while buzzer is on
            detectMotion(fb);
            break;
        }

        case DET_FACE_DETECT: {
            // Stage 2: Run ESP-WHO MTMN face detection
            float confidence = 0;
            if (detectFace(fb, &confidence)) {
                // Human confirmed!
                _result.confidence = confidence;
                _result.timestamp = now;
                _result.ready = true;
                enterState(DET_ALERT_READY);
            } else if (now - _stateEnteredAt >= DETECT_TIMEOUT_MS) {
                // Timeout — no face found, go back to idle
#ifdef DEBUG_MODE
                Serial.println("[DET] Face detect timeout, returning to IDLE");
#endif
                enterState(DET_IDLE);
            }
            // else: keep trying on next frame
            break;
        }

        default:
            break;
    }

    esp_camera_fb_return(fb);
}
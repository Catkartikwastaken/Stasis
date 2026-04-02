#include "human_detector.h"
#include "config.h"
#include "Arduino.h"
#include "fb_gfx.h"

HumanDetector::HumanDetector() : 
    _state(STATE_IDLE), 
    _prev_frame(NULL), 
    _alert_ready(false),
    _last_confidence(0.0),
    _last_alert_fb(NULL) {}

bool HumanDetector::init() {
    // Allocate buffer for 1-channel grayscale motion tracking (QVGA)
    _prev_frame = (uint8_t*)malloc(320 * 240);
    return _prev_frame != NULL;
}

void HumanDetector::setBuzzer(bool on) {
    digitalWrite(BUZZER_PIN, on ? HIGH : LOW);
}

bool HumanDetector::checkMotion(camera_fb_t* fb) {
    if (!fb || fb->format != PIXFORMAT_RGB565) return false;

    int changed_pixels = 0;
    int total_sampled = 0;
    
    // Sample pixels for STASIS Stage 1: > 3% delta
    for (int i = 0; i < fb->width * fb->height; i += 25) {
        uint16_t pixel = ((uint16_t*)fb->buf)[i];
        uint8_t luminance = (uint8_t)((pixel >> 5) & 0x3F); // Extract Green
        
        if (abs(luminance - _prev_frame[total_sampled]) > MOTION_THRESHOLD) {
            changed_pixels++;
        }
        _prev_frame[total_sampled++] = luminance;
    }

    return ((float)changed_pixels / total_sampled) > MOTION_RATIO;
}

bool HumanDetector::runInference(camera_fb_t* fb) {
    dl_matrix3du_t *image_matrix = dl_matrix3du_alloc(1, fb->width, fb->height, 3);
    if (!image_matrix) return false;

    if (!fmt2rgb888(fb->buf, fb->len, fb->format, image_matrix->item)) {
        dl_matrix3du_free(image_matrix);
        return false;
    }

    static mtmn_config_t mtmn_config = mtmn_init_config();
    box_array_t *faces = face_detect(image_matrix, &mtmn_config);
    
    bool detected = false;
    if (faces && faces->len > 0) {
        // Evaluate confidence against STASIS minimum 0.72
        if (faces->score[0] >= FACE_CONFIDENCE) {
            detected = true;
            _last_confidence = faces->score[0];
        }
        
        // Strict Memory Release
        free(faces->score);
        free(faces->box);
        free(faces->landmark);
        free(faces);
    }

    dl_matrix3du_free(image_matrix);
    return detected;
}

void HumanDetector::update() {
    unsigned long now = millis();

    if (_state == STATE_COOLDOWN) {
        if (now - _cooldown_timer > DETECT_COOLDOWN) {
            _state = STATE_IDLE;
        }
        return;
    }

    camera_fb_t* fb = esp_camera_fb_get();
    if (!fb) return;

    switch (_state) {
        case STATE_IDLE:
            if (checkMotion(fb)) {
                _state = STATE_TRACKING;
                _state_timer = now;
                setBuzzer(true);
            }
            break;

        case STATE_TRACKING:
            if (now - _state_timer > BUZZ_DURATION) {
                setBuzzer(false);
                _state = STATE_DETECTING;
                _state_timer = now; 
            }
            break;

        case STATE_DETECTING:
            if (runInference(fb)) {
                _alert_ready = true;
                _cooldown_timer = now;
                _last_alert_fb = fb; // Hold frame for JPEG conversion
                _state = STATE_COOLDOWN;
                return; // Do not return FB yet, UART needs it
            } else if (now - _state_timer > TRACK_TIMEOUT) {
                _state = STATE_IDLE;
            }
            break;
    }

    esp_camera_fb_return(fb);
}

bool HumanDetector::hasPendingAlert() {
    if (_alert_ready) {
        _alert_ready = false;
        return true;
    }
    return false;
}
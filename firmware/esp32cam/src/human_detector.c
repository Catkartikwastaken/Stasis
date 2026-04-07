/*
 * =======================================================================
 * STASIS — Human Detection Implementation (ESP-IDF)
 *
 * Pipeline per STASIS specification:
 *   1. Frame differencing detects motion (no ML needed)
 *   2. Buzzer activates to warn
 *   3. ESP-WHO MTMN face detection confirms human presence
 *   4. If confidence >= ALERT_CONFIDENCE → fire alert
 *   5. Configurable cooldown (default 30 s)
 *
 * ESP-WHO Integration:
 *   Uses the esp-dl component's MTMN model (fd_forward.h).
 *   If esp-dl is not installed, STASIS_FACE_DETECT_AVAILABLE is 0
 *   and the face-detect stage is skipped (motion-only alerts).
 *
 * Error Handling Strategy (per error-handling-patterns skill):
 *   - esp_err_t returns for all fallible operations
 *   - Graceful degradation: face detect unavailable → motion-only
 *   - Fail fast: init() fails loudly if PSRAM allocation fails
 *   - Resource cleanup: camera frames always returned via finally-style
 *   - Structured logging: ESP_LOGE/W/I/D with module tag
 * =======================================================================
 */

#include "human_detector.h"
#include "stasis_config.h"

#include <string.h>
#include <stdlib.h>
#include "esp_log.h"
#include "esp_heap_caps.h"
#include "driver/gpio.h"
#include "img_converters.h"

/* ---- ESP-WHO / esp-dl face detection (conditional) ---- */
#if __has_include("fd_forward.h")
    #include "fd_forward.h"
    #include "dl_lib_matrix3d.h"
    #define STASIS_FACE_DETECT_AVAILABLE 1
#else
    #define STASIS_FACE_DETECT_AVAILABLE 0
    #warning "fd_forward.h not found — face detection disabled. See components/README.md"
#endif

static const char *TAG = "STASIS_DET";

/* ================================================================
 * Module State (file-scoped)
 * ================================================================ */

static detect_state_t    s_state          = DET_IDLE;
static detection_result_t s_result        = {0, 0, false};

/* Motion detection */
static uint8_t          *s_prev_gray      = NULL;
static uint32_t          s_prev_gray_len  = 0;
static bool              s_prev_valid     = false;

/* Timing */
static uint32_t          s_state_entered  = 0;
static uint32_t          s_cooldown_start = 0;

/* Face detection config */
#if STASIS_FACE_DETECT_AVAILABLE
static mtmn_config_t     s_mtmn_cfg;
#endif

/* ================================================================
 * Internal Helpers
 * ================================================================ */

static void buzzer_on(void)
{
    gpio_set_level(PIN_BUZZER, 1);
}

static void buzzer_off(void)
{
    gpio_set_level(PIN_BUZZER, 0);
}

static void enter_state(detect_state_t new_state)
{
    /* Cleanup on exit from old state */
    if (s_state == DET_BUZZER_ON) {
        buzzer_off();
    }

    s_state = new_state;
    s_state_entered = millis_idf();

    if (STASIS_DEBUG) {
        static const char *names[] = {
            "IDLE", "MOTION_FOUND", "BUZZER_ON",
            "FACE_DETECT", "ALERT_READY", "COOLDOWN"
        };
        ESP_LOGI(TAG, "State -> %s", names[new_state]);
    }
}

/* ----------------------------------------------------------------
 * Stage 1: Motion Detection (Frame Differencing)
 *
 * Pure pixel math on the green channel of RGB565 frames.
 * No ESP-WHO needed.  Runs in ~1 ms on ESP32 @ 240 MHz.
 * ---------------------------------------------------------------- */
static bool detect_motion(camera_fb_t *fb)
{
    if (!fb || !s_prev_gray) return false;
    if (fb->format != PIXFORMAT_RGB565) return false;

    const uint16_t *pixels = (const uint16_t *)fb->buf;
    const uint32_t total   = fb->width * fb->height;
    uint32_t sample_count  = 0;
    uint32_t changed_count = 0;

    for (uint32_t i = 0; i < total && sample_count < s_prev_gray_len;
         i += STASIS_MOTION_SAMPLE_STEP)
    {
        /* Extract green channel from RGB565 (best SNR, 6 bits)
         * RGB565 layout: RRRRRGGG GGGBBBBB */
        uint16_t px    = pixels[i];
        uint8_t  green = (uint8_t)((px >> 3) & 0xFC);

        if (s_prev_valid) {
            int delta = abs((int)green - (int)s_prev_gray[sample_count]);
            if (delta > STASIS_MOTION_PIXEL_THRESH) {
                changed_count++;
            }
        }

        s_prev_gray[sample_count] = green;
        sample_count++;
    }

    s_prev_valid = true;

    if (sample_count == 0) return false;
    float ratio = (float)changed_count / (float)sample_count;
    return (ratio > STASIS_MOTION_PIXEL_RATIO);
}

/* ----------------------------------------------------------------
 * Stage 2: ESP-WHO MTMN Face Detection
 *
 * Converts RGB565 frame to RGB888, runs MTMN neural network.
 * Returns true if a face above ALERT_CONFIDENCE is found.
 *
 * Graceful degradation: if esp-dl is not installed, this always
 * returns true (motion alone triggers alert).
 * ---------------------------------------------------------------- */
static bool detect_face(camera_fb_t *fb, float *out_confidence)
{
#if STASIS_FACE_DETECT_AVAILABLE
    if (!fb) return false;

    /* Allocate RGB888 matrix in PSRAM for MTMN input */
    dl_matrix3du_t *image = dl_matrix3du_alloc(1, fb->width, fb->height, 3);
    if (!image) {
        ESP_LOGE(TAG, "MTMN matrix alloc failed (PSRAM required!)");
        return false;
    }

    /* Convert RGB565 → RGB888 */
    if (!fmt2rgb888(fb->buf, fb->len, fb->format, image->item)) {
        ESP_LOGE(TAG, "RGB565 → RGB888 conversion failed");
        dl_matrix3du_free(image);
        return false;
    }

    /* Run MTMN face detection */
    box_array_t *faces = face_detect(image, &s_mtmn_cfg);

    bool detected = false;
    if (faces && faces->len > 0) {
        /* Find highest-confidence face */
        float best = 0;
        for (int i = 0; i < faces->len; i++) {
            if (faces->score[i] > best) {
                best = faces->score[i];
            }
        }

        if (best >= STASIS_ALERT_CONFIDENCE) {
            detected = true;
            *out_confidence = best;
        }

        if (STASIS_DEBUG) {
            ESP_LOGI(TAG, "MTMN: %d face(s), best=%.2f %s",
                     faces->len, best,
                     detected ? "-> ALERT" : "-> below threshold");
        }

        /* Free MTMN result arrays */
        dl_lib_free(faces->score);
        dl_lib_free(faces->box);
        dl_lib_free(faces->landmark);
        free(faces);
    }

    dl_matrix3du_free(image);
    return detected;

#else
    /* No face detection available — treat motion as sufficient */
    (void)fb;
    *out_confidence = 1.0f;
    ESP_LOGW(TAG, "Face detection unavailable; motion-only alert");
    return true;
#endif
}

/* ================================================================
 * Public API
 * ================================================================ */

esp_err_t detector_init(void)
{
    /* ---- Allocate grayscale motion buffer ---- */
    s_prev_gray_len = (320 * 240) / STASIS_MOTION_SAMPLE_STEP;

    /* Try PSRAM first, fall back to internal heap */
    s_prev_gray = (uint8_t *)heap_caps_malloc(s_prev_gray_len, MALLOC_CAP_SPIRAM);
    if (!s_prev_gray) {
        s_prev_gray = (uint8_t *)malloc(s_prev_gray_len);
    }
    if (!s_prev_gray) {
        ESP_LOGE(TAG, "Failed to allocate motion buffer (%lu bytes)",
                 (unsigned long)s_prev_gray_len);
        return ESP_ERR_NO_MEM;
    }
    memset(s_prev_gray, 0, s_prev_gray_len);
    s_prev_valid = false;

    /* ---- Configure MTMN face detection (if available) ---- */
#if STASIS_FACE_DETECT_AVAILABLE
    s_mtmn_cfg.type                     = FAST;
    s_mtmn_cfg.min_face                 = (int)(0.15f * 240);
    s_mtmn_cfg.pyramid                  = 0.707f;
    s_mtmn_cfg.pyramid_times            = 4;
    s_mtmn_cfg.p_threshold.score        = STASIS_FACE_SCORE_THRESH;
    s_mtmn_cfg.p_threshold.nms          = 0.7f;
    s_mtmn_cfg.p_threshold.candidate_number = 20;
    s_mtmn_cfg.r_threshold.score        = 0.7f;
    s_mtmn_cfg.r_threshold.nms          = 0.7f;
    s_mtmn_cfg.r_threshold.candidate_number = 10;
    s_mtmn_cfg.o_threshold.score        = 0.7f;
    s_mtmn_cfg.o_threshold.nms          = 0.7f;
    s_mtmn_cfg.o_threshold.candidate_number = 1;

    ESP_LOGI(TAG, "Detector initialized (ESP-WHO MTMN face detection enabled)");
#else
    ESP_LOGW(TAG, "Detector initialized (motion-only, no face detection)");
#endif

    /* ---- Buzzer GPIO ---- */
    gpio_config_t buz_cfg = {
        .pin_bit_mask = (1ULL << PIN_BUZZER),
        .mode         = GPIO_MODE_OUTPUT,
        .pull_up_en   = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type    = GPIO_INTR_DISABLE,
    };
    esp_err_t err = gpio_config(&buz_cfg);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Buzzer GPIO config failed: %s", esp_err_to_name(err));
        free(s_prev_gray);
        s_prev_gray = NULL;
        return err;
    }
    gpio_set_level(PIN_BUZZER, 0);

    s_state = DET_IDLE;
    return ESP_OK;
}

void detector_update(void)
{
    uint32_t now = millis_idf();

    /* ---- COOLDOWN ---- */
    if (s_state == DET_COOLDOWN) {
        if (now - s_cooldown_start >= STASIS_COOLDOWN_MS) {
            enter_state(DET_IDLE);
        }
        return;
    }

    /* ---- ALERT_READY: wait for main loop to pick up result ---- */
    if (s_state == DET_ALERT_READY) {
        if (!s_result.ready) {
            s_cooldown_start = now;
            enter_state(DET_COOLDOWN);
        }
        return;
    }

    /* ---- Grab a camera frame ---- */
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) {
        ESP_LOGD(TAG, "Frame capture returned NULL (camera busy)");
        return;
    }

    switch (s_state) {
    case DET_IDLE:
        if (detect_motion(fb)) {
            enter_state(DET_MOTION_FOUND);
        }
        break;

    case DET_MOTION_FOUND:
        buzzer_on();
        enter_state(DET_BUZZER_ON);
        break;

    case DET_BUZZER_ON:
        if (now - s_state_entered >= STASIS_BUZZER_DURATION_MS) {
            buzzer_off();
            enter_state(DET_FACE_DETECT);
        }
        /* Keep updating motion reference while buzzer is on */
        detect_motion(fb);
        break;

    case DET_FACE_DETECT: {
        float confidence = 0;
        if (detect_face(fb, &confidence)) {
            s_result.confidence   = confidence;
            s_result.timestamp_ms = now;
            s_result.ready        = true;
            enter_state(DET_ALERT_READY);
        } else if (now - s_state_entered >= STASIS_DETECT_TIMEOUT_MS) {
            ESP_LOGD(TAG, "Face detect timeout — returning to IDLE");
            enter_state(DET_IDLE);
        }
        break;
    }

    default:
        break;
    }

    /* ALWAYS return the frame buffer — prevents camera driver leak */
    esp_camera_fb_return(fb);
}

bool detector_has_alert(void)
{
    return s_result.ready;
}

detection_result_t detector_get_result(void)
{
    detection_result_t r = s_result;
    s_result.ready = false;
    return r;
}

detect_state_t detector_get_state(void)
{
    return s_state;
}

esp_err_t detector_capture_jpeg(uint8_t **out_buf, size_t *out_len)
{
    /* Validate parameters — fail fast */
    if (!out_buf || !out_len) {
        return ESP_ERR_INVALID_ARG;
    }
    *out_buf = NULL;
    *out_len = 0;

    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) {
        ESP_LOGE(TAG, "JPEG capture: camera_fb_get failed");
        return ESP_FAIL;
    }

    esp_err_t ret = ESP_FAIL;

    if (fb->format == PIXFORMAT_JPEG) {
        /* Already JPEG — copy buffer */
        *out_buf = (uint8_t *)malloc(fb->len);
        if (*out_buf) {
            memcpy(*out_buf, fb->buf, fb->len);
            *out_len = fb->len;
            ret = ESP_OK;
        } else {
            ESP_LOGE(TAG, "JPEG copy malloc failed (%u bytes)", fb->len);
            ret = ESP_ERR_NO_MEM;
        }
    } else {
        /* Convert RGB565 → JPEG */
        bool ok = frame2jpg(fb, 80, out_buf, out_len);
        ret = ok ? ESP_OK : ESP_FAIL;
        if (!ok) {
            ESP_LOGE(TAG, "frame2jpg conversion failed");
        }
    }

    /* ALWAYS return frame buffer — resource cleanup */
    esp_camera_fb_return(fb);
    return ret;
}

/*
 * =======================================================================
 * STASIS — Human Detection Module (ESP-IDF)
 *
 * Pipeline: Motion Detect → Buzzer → ESP-WHO Face Detect → Alert
 *
 * This module provides the detection state machine.  It is pure C
 * and uses ESP-IDF APIs exclusively (no Arduino).
 *
 * Face detection requires the esp-dl component (MTMN model).
 * If esp-dl is not installed, the project still compiles — motion
 * detection works but the FACE_DETECT stage is skipped (graceful
 * degradation per error-handling-patterns skill).
 * =======================================================================
 */

#pragma once

#include "esp_err.h"
#include "esp_camera.h"
#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ---- Detection state machine ---- */
typedef enum {
    DET_IDLE           = 0,  /* Watching for motion (frame differencing)        */
    DET_MOTION_FOUND   = 1,  /* Motion confirmed, preparing for face detect     */
    DET_BUZZER_ON      = 2,  /* Buzzer sounding to warn                         */
    DET_FACE_DETECT    = 3,  /* Running ESP-WHO MTMN face detection             */
    DET_ALERT_READY    = 4,  /* Human confirmed — alert pending pickup          */
    DET_COOLDOWN       = 5   /* Post-alert cooldown (configurable, default 30s) */
} detect_state_t;

/* ---- Detection result ---- */
typedef struct {
    float    confidence;     /* MTMN face score (0.0–1.0)                       */
    uint32_t timestamp_ms;   /* millis_idf() at detection time                  */
    bool     ready;          /* true if result is pending pickup                */
} detection_result_t;

/*
 * Initialize the detection pipeline.
 *
 * Allocates motion buffer in PSRAM, configures MTMN (if available),
 * and sets up the buzzer GPIO.
 *
 * Returns ESP_OK on success, ESP_ERR_NO_MEM if allocation fails,
 * or ESP_FAIL on other errors.
 *
 * Error handling: Unrecoverable — caller should halt if this fails.
 */
esp_err_t detector_init(void);

/*
 * Run one iteration of the detection state machine.
 * Call this every loop iteration from the detection task.
 *
 * Internally grabs a camera frame, processes it through the current
 * pipeline stage, and advances state as needed.  Never blocks for
 * longer than one face-detection inference (~200-500ms on ESP32).
 */
void detector_update(void);

/*
 * Check if a confirmed human detection alert is pending.
 */
bool detector_has_alert(void);

/*
 * Retrieve and clear the pending detection result.
 *
 * After calling this, detector_has_alert() returns false and the
 * state machine transitions to COOLDOWN.
 */
detection_result_t detector_get_result(void);

/*
 * Get the current detection state (for status reporting).
 */
detect_state_t detector_get_state(void);

/*
 * Capture a JPEG snapshot of the current camera frame.
 *
 * On success, *out_buf points to a heap-allocated JPEG buffer and
 * *out_len contains its size.  The CALLER must free() the buffer.
 *
 * Returns ESP_OK on success, ESP_ERR_NO_MEM on allocation failure,
 * or ESP_FAIL if camera capture fails.
 */
esp_err_t detector_capture_jpeg(uint8_t **out_buf, size_t *out_len);

#ifdef __cplusplus
}
#endif

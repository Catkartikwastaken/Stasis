/*
 * =======================================================================
 * STASIS — MJPEG HTTP Stream Server (ESP-IDF)
 *
 * Uses esp_http_server (async, event-driven) instead of Arduino WebServer.
 *
 * Endpoints:
 *   GET /stream   — MJPEG multipart stream (continuous)
 *   GET /capture  — Single JPEG snapshot
 *   GET /status   — JSON status
 *
 * Error Handling:
 *   - All handlers return esp_err_t
 *   - Camera failures return HTTP 500 with descriptive body
 *   - Frame buffer is ALWAYS returned (even on error paths)
 * =======================================================================
 */

#pragma once

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Start the HTTP server on STASIS_STREAM_PORT (default 81).
 *
 * Must be called AFTER WiFi is connected and camera is initialized.
 *
 * Returns ESP_OK on success, or an error if the server fails to start.
 */
esp_err_t stream_server_start(void);

/*
 * Stop the HTTP server and release resources.
 *
 * Safe to call even if server was never started.
 */
void stream_server_stop(void);

#ifdef __cplusplus
}
#endif

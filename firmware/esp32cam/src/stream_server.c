/*
 * =======================================================================
 * STASIS — MJPEG HTTP Stream Server Implementation (ESP-IDF)
 *
 * Uses esp_http_server instead of Arduino WebServer.
 * The MJPEG handler blocks its task context while streaming;
 * esp_http_server uses a dedicated thread so the main loop is
 * not affected.
 *
 * Error Handling Strategy:
 *   - Every camera frame capture is checked; on failure we send
 *     HTTP 500 and break out of the stream loop.
 *   - JPEG conversion failures are logged and the frame is skipped
 *     (not fatal — next frame may succeed).
 *   - Resource cleanup: camera frame buffers are ALWAYS returned.
 *   - httpd_send errors break the stream (client disconnected).
 * =======================================================================
 */

#include "stream_server.h"
#include "stasis_config.h"

#include <string.h>
#include "esp_log.h"
#include "esp_camera.h"
#include "esp_http_server.h"
#include "img_converters.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "STASIS_STREAM";

static httpd_handle_t s_httpd = NULL;

/* MJPEG multipart boundary */
#define STREAM_BOUNDARY      "stasisframe"
#define STREAM_CONTENT_TYPE  "multipart/x-mixed-replace;boundary=" STREAM_BOUNDARY
#define PART_HEADER          "\r\n--" STREAM_BOUNDARY "\r\n" \
                             "Content-Type: image/jpeg\r\n" \
                             "Content-Length: %u\r\n\r\n"

/* ================================================================
 * GET /stream — MJPEG continuous stream
 *
 * This handler blocks until the client disconnects.
 * esp_http_server runs handlers in a dedicated thread, so the
 * main detection loop is not affected.
 * ================================================================ */
static esp_err_t handle_stream(httpd_req_t *req)
{
    esp_err_t res;
    char part_buf[128];

    ESP_LOGI(TAG, "Stream client connected from %d", httpd_req_to_sockfd(req));

    res = httpd_resp_set_type(req, STREAM_CONTENT_TYPE);
    if (res != ESP_OK) return res;

    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    httpd_resp_set_hdr(req, "Cache-Control", "no-cache");

    while (true) {
        camera_fb_t *fb = esp_camera_fb_get();
        if (!fb) {
            ESP_LOGE(TAG, "Stream: camera capture failed");
            httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR,
                                "Camera capture failed");
            return ESP_FAIL;
        }

        uint8_t *jpg_buf  = NULL;
        size_t   jpg_len  = 0;
        bool     converted = false;

        if (fb->format == PIXFORMAT_JPEG) {
            jpg_buf = fb->buf;
            jpg_len = fb->len;
        } else {
            converted = frame2jpg(fb, 80, &jpg_buf, &jpg_len);
            if (!converted) {
                ESP_LOGW(TAG, "Stream: JPEG conversion failed, skipping frame");
                esp_camera_fb_return(fb);
                continue;   /* Skip this frame, try next */
            }
        }

        /* Send multipart boundary + JPEG data */
        int hdr_len = snprintf(part_buf, sizeof(part_buf),
                               PART_HEADER, (unsigned)jpg_len);

        res = httpd_send(req, part_buf, hdr_len);
        if (res == ESP_OK) {
            res = httpd_send(req, (const char *)jpg_buf, jpg_len);
        }

        /* Cleanup — ALWAYS free resources */
        if (converted && jpg_buf) free(jpg_buf);
        esp_camera_fb_return(fb);

        if (res != ESP_OK) {
            ESP_LOGI(TAG, "Stream client disconnected");
            break;
        }

        vTaskDelay(pdMS_TO_TICKS(STASIS_STREAM_FPS_DELAY_MS));
    }

    return res;
}

/* ================================================================
 * GET /capture — Single JPEG snapshot
 * ================================================================ */
static esp_err_t handle_capture(httpd_req_t *req)
{
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) {
        ESP_LOGE(TAG, "Capture: camera failed");
        httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR,
                            "Camera capture failed");
        return ESP_FAIL;
    }

    uint8_t *jpg_buf  = NULL;
    size_t   jpg_len  = 0;
    bool     converted = false;
    esp_err_t ret      = ESP_OK;

    if (fb->format == PIXFORMAT_JPEG) {
        jpg_buf = fb->buf;
        jpg_len = fb->len;
    } else {
        converted = frame2jpg(fb, 80, &jpg_buf, &jpg_len);
        if (!converted) {
            ESP_LOGE(TAG, "Capture: JPEG conversion failed");
            esp_camera_fb_return(fb);
            httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR,
                                "JPEG conversion failed");
            return ESP_FAIL;
        }
    }

    httpd_resp_set_type(req, "image/jpeg");
    httpd_resp_set_hdr(req, "Content-Disposition",
                       "inline; filename=stasis_capture.jpg");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");

    ret = httpd_resp_send(req, (const char *)jpg_buf, jpg_len);

    if (converted && jpg_buf) free(jpg_buf);
    esp_camera_fb_return(fb);

    return ret;
}

/* ================================================================
 * GET /status — JSON status
 * ================================================================ */
static esp_err_t handle_status(httpd_req_t *req)
{
    /* Retrieve heap info for diagnostics */
    size_t free_heap   = esp_get_free_heap_size();
    size_t free_psram  = heap_caps_get_free_size(MALLOC_CAP_SPIRAM);

    char json[256];
    int len = snprintf(json, sizeof(json),
        "{\"status\":\"online\",\"stream\":true,"
        "\"model\":\"AI-THINKER\",\"framework\":\"ESP-IDF\","
        "\"face_detect\":%s,"
        "\"free_heap\":%u,\"free_psram\":%u}",
#if __has_include("fd_forward.h")
        "true",
#else
        "false",
#endif
        (unsigned)free_heap, (unsigned)free_psram);

    httpd_resp_set_type(req, "application/json");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    return httpd_resp_send(req, json, len);
}

/* ================================================================
 * Public API
 * ================================================================ */

esp_err_t stream_server_start(void)
{
    if (s_httpd) {
        ESP_LOGW(TAG, "Server already running");
        return ESP_OK;
    }

    httpd_config_t config   = HTTPD_DEFAULT_CONFIG();
    config.server_port      = STASIS_STREAM_PORT;
    config.ctrl_port        = STASIS_STREAM_PORT + 1;
    config.stack_size       = 8192;   /* Larger stack for JPEG conversion */
    config.max_uri_handlers = 4;

    esp_err_t err = httpd_start(&s_httpd, &config);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to start HTTP server: %s", esp_err_to_name(err));
        return err;
    }

    /* Register URI handlers */
    const httpd_uri_t uri_stream = {
        .uri      = "/stream",
        .method   = HTTP_GET,
        .handler  = handle_stream,
        .user_ctx = NULL,
    };
    const httpd_uri_t uri_capture = {
        .uri      = "/capture",
        .method   = HTTP_GET,
        .handler  = handle_capture,
        .user_ctx = NULL,
    };
    const httpd_uri_t uri_status = {
        .uri      = "/status",
        .method   = HTTP_GET,
        .handler  = handle_status,
        .user_ctx = NULL,
    };

    httpd_register_uri_handler(s_httpd, &uri_stream);
    httpd_register_uri_handler(s_httpd, &uri_capture);
    httpd_register_uri_handler(s_httpd, &uri_status);

    ESP_LOGI(TAG, "HTTP server started on port %d", STASIS_STREAM_PORT);
    return ESP_OK;
}

void stream_server_stop(void)
{
    if (s_httpd) {
        httpd_stop(s_httpd);
        s_httpd = NULL;
        ESP_LOGI(TAG, "HTTP server stopped");
    }
}

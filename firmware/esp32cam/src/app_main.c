/*
 * =======================================================================
 * STASIS — ESP32-CAM Main Entry Point (ESP-IDF)
 *
 * Framework:  ESP-IDF via PlatformIO
 * Hardware:   AI-Thinker ESP32-CAM
 *
 * This file replaces the Arduino main.ino.  All Arduino APIs
 * (Serial, WiFi, WebServer, pinMode, etc.) are replaced with
 * their ESP-IDF equivalents.
 *
 * Startup sequence:
 *   1. UART init           — communication to ESP32-S3
 *   2. NVS init            — required by WiFi driver
 *   3. Camera init         — RGB565, QVGA, 1 frame buffer
 *   4. Detector init       — motion buffer + MTMN config
 *   5. WiFi STA connect    — event-driven with timeout
 *   6. HTTP stream server  — started only after WiFi connects
 *   7. Detection task      — FreeRTOS task running the pipeline
 *
 * Error Handling Strategy (per error-handling-patterns skill):
 *   - Unrecoverable: NVS, camera, detector init failures → halt
 *   - Recoverable: WiFi timeout → detection still runs (no stream)
 *   - Graceful degradation: face detect unavailable → motion-only
 *   - Resource cleanup: event handlers, GPIO, camera frames
 * =======================================================================
 */

#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"
#include "esp_log.h"
#include "esp_system.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_camera.h"
#include "nvs_flash.h"
#include "driver/gpio.h"

#include "stasis_config.h"
#include "human_detector.h"
#include "stream_server.h"
#include "uart_comms.h"

static const char *TAG = "STASIS_MAIN";

/* ================================================================
 * WiFi — Event-Driven Connection
 *
 * Uses FreeRTOS EventGroup to signal connection result.
 * Much more robust than Arduino's polling WiFi.status().
 * ================================================================ */

#define WIFI_CONNECTED_BIT  BIT0
#define WIFI_FAIL_BIT       BIT1

static EventGroupHandle_t s_wifi_event_group = NULL;
static int                s_wifi_retry_count = 0;
#define WIFI_MAX_RETRY      3

static void wifi_event_handler(void *arg, esp_event_base_t event_base,
                               int32_t event_id, void *event_data)
{
    if (event_base == WIFI_EVENT) {
        switch (event_id) {
        case WIFI_EVENT_STA_START:
            ESP_LOGI(TAG, "WiFi STA started, connecting...");
            esp_wifi_connect();
            break;

        case WIFI_EVENT_STA_DISCONNECTED:
            if (s_wifi_retry_count < WIFI_MAX_RETRY) {
                s_wifi_retry_count++;
                ESP_LOGW(TAG, "WiFi disconnected, retry %d/%d",
                         s_wifi_retry_count, WIFI_MAX_RETRY);
                esp_wifi_connect();
            } else {
                ESP_LOGE(TAG, "WiFi connection failed after %d retries",
                         WIFI_MAX_RETRY);
                xEventGroupSetBits(s_wifi_event_group, WIFI_FAIL_BIT);
            }
            break;

        default:
            break;
        }
    } else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *event = (ip_event_got_ip_t *)event_data;
        ESP_LOGI(TAG, "Got IP: " IPSTR, IP2STR(&event->ip_info.ip));
        s_wifi_retry_count = 0;
        xEventGroupSetBits(s_wifi_event_group, WIFI_CONNECTED_BIT);
    }
}

/*
 * Initialize WiFi in STA mode and wait for connection.
 *
 * Returns ESP_OK if connected, ESP_ERR_TIMEOUT if connection
 * timed out (detection will still work, just no streaming).
 */
static esp_err_t wifi_init_sta(void)
{
    s_wifi_event_group = xEventGroupCreate();
    if (!s_wifi_event_group) {
        ESP_LOGE(TAG, "Failed to create WiFi event group");
        return ESP_ERR_NO_MEM;
    }

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    /* Register event handlers */
    esp_event_handler_instance_t inst_any_id;
    esp_event_handler_instance_t inst_got_ip;

    ESP_ERROR_CHECK(esp_event_handler_instance_register(
        WIFI_EVENT, ESP_EVENT_ANY_ID,
        &wifi_event_handler, NULL, &inst_any_id));

    ESP_ERROR_CHECK(esp_event_handler_instance_register(
        IP_EVENT, IP_EVENT_STA_GOT_IP,
        &wifi_event_handler, NULL, &inst_got_ip));

    /* Configure and start WiFi */
    wifi_config_t wifi_config = {
        .sta = {
            .threshold.authmode = WIFI_AUTH_WPA2_PSK,
            .pmf_cfg = {
                .capable  = true,
                .required = false,
            },
        },
    };

    /* Copy SSID and password from Kconfig values */
    strncpy((char *)wifi_config.sta.ssid,
            STASIS_WIFI_SSID, sizeof(wifi_config.sta.ssid) - 1);
    strncpy((char *)wifi_config.sta.password,
            STASIS_WIFI_PASS, sizeof(wifi_config.sta.password) - 1);

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());

    /* Wait for connection or timeout */
    EventBits_t bits = xEventGroupWaitBits(
        s_wifi_event_group,
        WIFI_CONNECTED_BIT | WIFI_FAIL_BIT,
        pdFALSE, pdFALSE,
        pdMS_TO_TICKS(STASIS_WIFI_TIMEOUT_MS));

    if (bits & WIFI_CONNECTED_BIT) {
        ESP_LOGI(TAG, "WiFi connected to %s", STASIS_WIFI_SSID);
        return ESP_OK;
    }

    ESP_LOGW(TAG, "WiFi connection timed out — streaming unavailable");
    return ESP_ERR_TIMEOUT;
}

/* ================================================================
 * Camera Initialization
 * ================================================================ */
static esp_err_t camera_init(void)
{
    camera_config_t cam_cfg = {
        .pin_pwdn     = CAM_PIN_PWDN,
        .pin_reset    = CAM_PIN_RESET,
        .pin_xclk     = CAM_PIN_XCLK,
        .pin_sccb_sda = CAM_PIN_SIOD,
        .pin_sccb_scl = CAM_PIN_SIOC,
        .pin_d7       = CAM_PIN_D7,
        .pin_d6       = CAM_PIN_D6,
        .pin_d5       = CAM_PIN_D5,
        .pin_d4       = CAM_PIN_D4,
        .pin_d3       = CAM_PIN_D3,
        .pin_d2       = CAM_PIN_D2,
        .pin_d1       = CAM_PIN_D1,
        .pin_d0       = CAM_PIN_D0,
        .pin_vsync    = CAM_PIN_VSYNC,
        .pin_href     = CAM_PIN_HREF,
        .pin_pclk     = CAM_PIN_PCLK,

        .xclk_freq_hz = 20000000,
        .ledc_timer   = LEDC_TIMER_0,
        .ledc_channel = LEDC_CHANNEL_0,

        /* RGB565 required for motion detection and ESP-WHO face detect */
        .pixel_format = PIXFORMAT_RGB565,
        .frame_size   = FRAMESIZE_QVGA,     /* 320x240 */
        .fb_count     = 1,                   /* Save PSRAM for MTMN */
        .fb_location  = CAMERA_FB_IN_PSRAM,
        .grab_mode    = CAMERA_GRAB_WHEN_EMPTY,
        .jpeg_quality = 12,
    };

    esp_err_t err = esp_camera_init(&cam_cfg);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Camera init failed: %s (0x%x)",
                 esp_err_to_name(err), err);
        return err;
    }

    ESP_LOGI(TAG, "Camera initialized (RGB565, QVGA, 1 FB in PSRAM)");
    return ESP_OK;
}

/* ================================================================
 * Flash LED GPIO
 * ================================================================ */
static esp_err_t flash_led_init(void)
{
    gpio_config_t io_cfg = {
        .pin_bit_mask = (1ULL << PIN_FLASH_LED),
        .mode         = GPIO_MODE_OUTPUT,
        .pull_up_en   = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type    = GPIO_INTR_DISABLE,
    };
    esp_err_t err = gpio_config(&io_cfg);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "Flash LED GPIO config failed: %s", esp_err_to_name(err));
        return err;
    }
    gpio_set_level(PIN_FLASH_LED, 0);
    return ESP_OK;
}

/* ================================================================
 * Detection Task (FreeRTOS)
 *
 * Runs the detection state machine and sends alerts over UART.
 * This is cleaner than a bare loop() — FreeRTOS manages scheduling,
 * watchdog feeding, and stack monitoring.
 * ================================================================ */
static void detection_task(void *pvParameters)
{
    (void)pvParameters;
    ESP_LOGI(TAG, "Detection task started");

    while (true) {
        /* Run one iteration of the detection state machine */
        detector_update();

        /* Check for confirmed human alert */
        if (detector_has_alert()) {
            detection_result_t result = detector_get_result();

            ESP_LOGI(TAG, "HUMAN DETECTED! confidence=%.2f timestamp=%lu",
                     result.confidence, (unsigned long)result.timestamp_ms);

            /* Capture JPEG snapshot for UART alert */
            uint8_t *jpg_buf = NULL;
            size_t   jpg_len = 0;
            esp_err_t cap_err = detector_capture_jpeg(&jpg_buf, &jpg_len);

            if (cap_err == ESP_OK && jpg_buf) {
                uart_comms_send_alert(result.confidence, jpg_buf, jpg_len);
                free(jpg_buf);
            } else {
                /* Graceful degradation: send alert without image */
                ESP_LOGW(TAG, "JPEG capture failed, sending alert without image");
                uart_comms_send_alert(result.confidence, NULL, 0);
            }
        }

        /* Yield to other tasks — 10ms tick for responsive detection */
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

/* ================================================================
 * NVS Initialization
 *
 * NVS is required by the WiFi driver for storing calibration data.
 * If NVS partition is full/corrupted, erase and re-init.
 * ================================================================ */
static esp_err_t nvs_init(void)
{
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES ||
        ret == ESP_ERR_NVS_NEW_VERSION_FOUND)
    {
        ESP_LOGW(TAG, "NVS partition issue (%s), erasing...",
                 esp_err_to_name(ret));
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    return ret;
}

/* ================================================================
 * app_main — ESP-IDF Entry Point
 *
 * This replaces Arduino's setup() + loop().
 * The detection loop runs in a dedicated FreeRTOS task.
 * ================================================================ */
void app_main(void)
{
    ESP_LOGI(TAG, "===========================================");
    ESP_LOGI(TAG, "  STASIS ESP32-CAM — ESP-IDF / PlatformIO  ");
    ESP_LOGI(TAG, "===========================================");
    ESP_LOGI(TAG, "Free heap: %u bytes", (unsigned)esp_get_free_heap_size());
    ESP_LOGI(TAG, "Free PSRAM: %u bytes",
             (unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM));

    /* ---- 1. NVS (required by WiFi) ---- */
    esp_err_t err = nvs_init();
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "FATAL: NVS init failed: %s", esp_err_to_name(err));
        return;   /* Halt — unrecoverable */
    }

    /* ---- 2. UART (communication to ESP32-S3) ---- */
    err = uart_comms_init();
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "FATAL: UART init failed: %s", esp_err_to_name(err));
        return;
    }
    uart_comms_send_log("STASIS_CAM_BOOTING");

    /* ---- 3. Flash LED ---- */
    flash_led_init();   /* Non-fatal if this fails */

    /* ---- 4. Camera ---- */
    err = camera_init();
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "FATAL: Camera init failed");
        uart_comms_send_log("camera_init_fail");
        return;
    }

    /* ---- 5. Detection Pipeline ---- */
    err = detector_init();
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "FATAL: Detector init failed");
        uart_comms_send_log("detector_init_fail");
        return;
    }

    /* ---- 6. WiFi (recoverable — detection works without it) ---- */
    err = wifi_init_sta();
    if (err == ESP_OK) {
        /* ---- 7. HTTP Stream Server (only with WiFi) ---- */
        err = stream_server_start();
        if (err == ESP_OK) {
            uart_comms_send_log("STREAM_READY");
        } else {
            ESP_LOGW(TAG, "Stream server failed to start: %s",
                     esp_err_to_name(err));
            uart_comms_send_log("stream_server_fail");
        }
    } else {
        uart_comms_send_log("wifi_timeout");
        ESP_LOGW(TAG, "Running in detection-only mode (no streaming)");
    }

    /* ---- 8. Start Detection Task ---- */
    BaseType_t task_ok = xTaskCreatePinnedToCore(
        detection_task,
        "stasis_det",
        8192,               /* Stack size — face detection needs headroom */
        NULL,
        5,                  /* Priority (higher than idle, lower than WiFi) */
        NULL,
        1                   /* Pin to core 1 (core 0 handles WiFi) */
    );

    if (task_ok != pdPASS) {
        ESP_LOGE(TAG, "FATAL: Failed to create detection task");
        uart_comms_send_log("task_create_fail");
        return;
    }

    uart_comms_send_log("STASIS_CAM_ONLINE");
    ESP_LOGI(TAG, "Startup complete — detection pipeline active");
    ESP_LOGI(TAG, "Free heap after init: %u bytes",
             (unsigned)esp_get_free_heap_size());

    /* app_main returns — FreeRTOS scheduler runs detection_task and
     * esp_http_server handles HTTP requests in their own threads. */
}

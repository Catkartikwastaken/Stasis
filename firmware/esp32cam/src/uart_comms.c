/*
 * =======================================================================
 * STASIS — UART Communication Implementation (ESP-IDF)
 *
 * Uses ESP-IDF UART driver and mbedTLS Base64 encoding.
 * No Arduino dependencies.
 *
 * Error Handling Strategy:
 *   - UART driver errors during init are propagated via esp_err_t
 *   - Send failures are logged but non-fatal (best-effort delivery)
 *   - Base64 is done in fixed 48-byte chunks to avoid large allocs
 *   - Input validation: null msg rejected, null image sends alert
 *     without image field
 * =======================================================================
 */

#include "uart_comms.h"
#include "stasis_config.h"

#include <string.h>
#include <stdio.h>
#include "esp_log.h"
#include "driver/uart.h"
#include "mbedtls/base64.h"

static const char *TAG = "STASIS_UART";

/* UART RX/TX buffer sizes */
#define UART_BUF_SIZE  1024

/* ================================================================
 * Internal: write raw bytes to UART
 * ================================================================ */
static void uart_write(const char *data, size_t len)
{
    uart_write_bytes(STASIS_UART_NUM, data, len);
}

static void uart_print(const char *str)
{
    uart_write(str, strlen(str));
}

/* ================================================================
 * Internal: Base64-encode and send in fixed-size chunks
 *
 * 48 raw bytes → 64 base64 chars (no padding alignment issues).
 * Uses a small stack buffer — no heap allocation needed.
 * ================================================================ */
static void uart_send_base64_chunked(const uint8_t *buf, size_t len)
{
    const size_t CHUNK_RAW = 48;
    unsigned char out[65];  /* 64 base64 chars + NUL */
    size_t olen = 0;

    for (size_t i = 0; i < len; i += CHUNK_RAW) {
        size_t chunk = len - i;
        if (chunk > CHUNK_RAW) chunk = CHUNK_RAW;

        int ret = mbedtls_base64_encode(out, sizeof(out), &olen, buf + i, chunk);
        if (ret != 0) {
            ESP_LOGE(TAG, "Base64 encode failed at offset %u (ret=%d)",
                     (unsigned)i, ret);
            return;
        }

        out[olen] = '\0';
        uart_print((const char *)out);
    }
}

/* ================================================================
 * Public API
 * ================================================================ */

esp_err_t uart_comms_init(void)
{
    const uart_config_t uart_cfg = {
        .baud_rate  = STASIS_UART_BAUD,
        .data_bits  = UART_DATA_8_BITS,
        .parity     = UART_PARITY_DISABLE,
        .stop_bits  = UART_STOP_BITS_1,
        .flow_ctrl  = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_APB,
    };

    esp_err_t err;

    err = uart_param_config(STASIS_UART_NUM, &uart_cfg);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "uart_param_config failed: %s", esp_err_to_name(err));
        return err;
    }

    err = uart_set_pin(STASIS_UART_NUM,
                       STASIS_UART_TX, STASIS_UART_RX,
                       UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "uart_set_pin failed: %s", esp_err_to_name(err));
        return err;
    }

    err = uart_driver_install(STASIS_UART_NUM,
                              UART_BUF_SIZE, UART_BUF_SIZE,
                              0, NULL, 0);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "uart_driver_install failed: %s", esp_err_to_name(err));
        return err;
    }

    ESP_LOGI(TAG, "UART%d initialized @ %d baud", STASIS_UART_NUM, STASIS_UART_BAUD);
    return ESP_OK;
}

esp_err_t uart_comms_send_alert(float confidence,
                                const uint8_t *jpg_buf, size_t jpg_len)
{
    char hdr[128];

    if (jpg_buf && jpg_len > 0) {
        /* Full alert with image */
        int len = snprintf(hdr, sizeof(hdr),
            "{\"event\":\"human_detected\",\"confidence\":%.2f,"
            "\"timestamp\":%lu,\"image\":\"",
            confidence, (unsigned long)millis_idf());
        uart_write(hdr, len);

        uart_send_base64_chunked(jpg_buf, jpg_len);

        uart_print("\"}\n");
    } else {
        /* Alert without image */
        int len = snprintf(hdr, sizeof(hdr),
            "{\"event\":\"human_detected\",\"confidence\":%.2f,"
            "\"timestamp\":%lu}\n",
            confidence, (unsigned long)millis_idf());
        uart_write(hdr, len);

        ESP_LOGW(TAG, "Alert sent without image (capture unavailable)");
    }

    return ESP_OK;
}

esp_err_t uart_comms_send_log(const char *msg)
{
    if (!msg) {
        return ESP_ERR_INVALID_ARG;
    }

    char buf[256];
    int len = snprintf(buf, sizeof(buf), "{\"log\":\"%s\"}\n", msg);

    /* Truncation check — log it but don't fail */
    if (len >= (int)sizeof(buf)) {
        ESP_LOGW(TAG, "Log message truncated (%d > %d)", len, (int)sizeof(buf));
        len = sizeof(buf) - 1;
    }

    uart_write(buf, len);
    return ESP_OK;
}

/*
 * =======================================================================
 * STASIS — UART Communication Module (ESP-IDF)
 *
 * Sends JSON messages to the ESP32-S3 main controller.
 * Uses the ESP-IDF UART driver (not Arduino Serial).
 *
 * Protocol:
 *   Alert:  {"event":"human_detected","confidence":0.85,"timestamp":12345,"image":"<base64>"}
 *   Log:    {"log":"message_here"}
 *
 * Error Handling:
 *   - esp_err_t returns for init and send operations
 *   - Base64 encoding in fixed-size chunks (no large heap alloc)
 *   - Null/zero-length image handled gracefully (alert without image)
 * =======================================================================
 */

#pragma once

#include "esp_err.h"
#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Initialize the UART driver for communication to ESP32-S3.
 *
 * Configures UART_NUM_0 at STASIS_UART_BAUD (default 115200).
 *
 * Returns ESP_OK on success or an error from uart_driver_install.
 */
esp_err_t uart_comms_init(void);

/*
 * Send a human-detected alert with optional JPEG snapshot.
 *
 * jpg_buf/jpg_len: Pre-captured JPEG data.  If NULL/0, the alert
 *                  is sent without an image field.
 *
 * Returns ESP_OK if the full message was written to the UART TX buffer.
 */
esp_err_t uart_comms_send_alert(float confidence,
                                const uint8_t *jpg_buf, size_t jpg_len);

/*
 * Send a JSON log message.
 *
 * Returns ESP_OK on success, ESP_ERR_INVALID_ARG if msg is NULL.
 */
esp_err_t uart_comms_send_log(const char *msg);

#ifdef __cplusplus
}
#endif

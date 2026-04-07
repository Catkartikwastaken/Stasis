/*
 * =======================================================================
 * STASIS — ESP32-CAM Configuration Header (ESP-IDF)
 *
 * Hardware:   AI-Thinker ESP32-CAM
 * Framework:  ESP-IDF via PlatformIO
 *
 * This file maps Kconfig values (from menuconfig) to compile-time
 * constants plus hardware pin definitions that don't change.
 * =======================================================================
 */

#pragma once

#include "sdkconfig.h"
#include <stdint.h>
#include "esp_timer.h"

/* ---- Convenience: millis() equivalent for ESP-IDF ---- */
static inline uint32_t millis_idf(void)
{
    return (uint32_t)(esp_timer_get_time() / 1000ULL);
}

/* ================================================================
 * HARDWARE PINS — AI-Thinker ESP32-CAM
 * These are fixed by PCB layout and never change.
 * ================================================================ */

/* Camera data pins */
#define CAM_PIN_PWDN      32
#define CAM_PIN_RESET     (-1)   /* Not connected */
#define CAM_PIN_XCLK       0
#define CAM_PIN_SIOD      26
#define CAM_PIN_SIOC      27
#define CAM_PIN_D7        35
#define CAM_PIN_D6        34
#define CAM_PIN_D5        39
#define CAM_PIN_D4        36
#define CAM_PIN_D3        21
#define CAM_PIN_D2        19
#define CAM_PIN_D1        18
#define CAM_PIN_D0         5
#define CAM_PIN_VSYNC     25
#define CAM_PIN_HREF      23
#define CAM_PIN_PCLK      22

/* Built-in flash LED */
#define PIN_FLASH_LED      4

/* Buzzer (connected to GPIO2) */
#define PIN_BUZZER         2

/* UART TX/RX — shared with Serial/programming pins on AI-Thinker */
#define STASIS_UART_NUM    UART_NUM_0
#define STASIS_UART_TX     1
#define STASIS_UART_RX     3

/* ================================================================
 * CONFIGURABLE VALUES — sourced from Kconfig (menuconfig)
 * Defaults are set in Kconfig.projbuild.
 * ================================================================ */

/* WiFi */
#define STASIS_WIFI_SSID           CONFIG_STASIS_WIFI_SSID
#define STASIS_WIFI_PASS           CONFIG_STASIS_WIFI_PASS
#define STASIS_WIFI_TIMEOUT_MS     CONFIG_STASIS_WIFI_TIMEOUT_MS

/* UART */
#define STASIS_UART_BAUD           CONFIG_STASIS_UART_BAUD

/* HTTP server */
#define STASIS_STREAM_PORT         CONFIG_STASIS_STREAM_PORT

/* Detection pipeline — Stage 1: motion */
#define STASIS_MOTION_PIXEL_THRESH CONFIG_STASIS_MOTION_PIXEL_THRESHOLD
#define STASIS_MOTION_PIXEL_RATIO  (CONFIG_STASIS_MOTION_PIXEL_RATIO / 1000.0f)
#define STASIS_MOTION_SAMPLE_STEP  CONFIG_STASIS_MOTION_SAMPLE_STEP

/* Detection pipeline — Stage 2: face (MTMN) */
#define STASIS_FACE_SCORE_THRESH   (CONFIG_STASIS_FACE_SCORE_THRESHOLD / 100.0f)
#define STASIS_ALERT_CONFIDENCE    (CONFIG_STASIS_ALERT_CONFIDENCE / 100.0f)

/* Timing */
#define STASIS_COOLDOWN_MS         CONFIG_STASIS_DETECT_COOLDOWN_MS
#define STASIS_BUZZER_DURATION_MS  CONFIG_STASIS_BUZZER_DURATION_MS
#define STASIS_DETECT_TIMEOUT_MS   CONFIG_STASIS_DETECT_TIMEOUT_MS
#define STASIS_STREAM_FPS_DELAY_MS CONFIG_STASIS_STREAM_FPS_DELAY_MS

/* Debug */
#ifdef CONFIG_STASIS_DEBUG_MODE
#define STASIS_DEBUG 1
#else
#define STASIS_DEBUG 0
#endif

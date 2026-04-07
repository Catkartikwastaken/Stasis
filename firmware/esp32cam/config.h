#pragma once

// =====================================================================
// STASIS — ESP32-CAM Configuration (AI-Thinker Module)
// Arduino IDE Board: "AI Thinker ESP32-CAM"
// Partition: "Huge APP (3MB No OTA/1MB SPIFFS)"
// PSRAM: "Enabled"
// ESP32 Arduino Core: 2.0.x
// =====================================================================

// ---- Camera Model: AI-THINKER ----
#define CAMERA_MODEL_AI_THINKER

#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

// ---- Flash LED (built-in on AI-Thinker) ----
#define FLASH_LED_PIN      4

// ---- UART to ESP32-S3 ----
// AI-Thinker ESP32-CAM: U0TXD = GPIO1, U0RXD = GPIO3
// These are also the programming pins — UART is shared with Serial
#define UART_BAUD         115200

// ---- Buzzer ----
#define BUZZER_PIN         2

// ---- WiFi for MJPEG streaming ----
#define CAM_WIFI_SSID     "STASIS_NET"
#define CAM_WIFI_PASS     "stasis2024"
#define CAM_WIFI_TIMEOUT  15000

// ---- Detection Pipeline Thresholds ----
// Stage 1: Frame differencing motion detection
#define MOTION_PIXEL_THRESHOLD  25      // Grayscale delta per pixel
#define MOTION_PIXEL_RATIO      0.03f   // 3% of sampled pixels must change
#define MOTION_SAMPLE_STEP      4       // Sample every Nth pixel (speed vs accuracy)

// Stage 2: ESP-WHO face detection (MTMN network)
// min_face: minimum face size as fraction of frame (0.0–1.0)
// Higher = faster but misses small/distant faces
// Lower = catches distant faces but slower
#define FACE_MIN_SIZE           0.15f
// score_threshold: MTMN detection confidence (0.0–1.0)
#define FACE_SCORE_THRESHOLD    0.60f
// STASIS alert confidence: only fire alert above this
#define ALERT_CONFIDENCE        0.72f

// ---- Timing ----
#define DETECT_COOLDOWN_MS  30000   // 30s between alerts
#define BUZZER_DURATION_MS  500     // Buzzer on-time after motion
#define MOTION_TO_DETECT_MS 200     // Settle time before running face detect
#define DETECT_TIMEOUT_MS   8000    // Max time to try face detect after motion

// ---- Stream ----
#define STREAM_PORT         81
#define STREAM_FPS_DELAY    66      // ~15 fps

// ---- Debug ----
// Uncomment to enable verbose serial output
// #define DEBUG_MODE
#pragma once

// Camera Model: AI THINKER
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

// UART Communications (To ESP32-S3)
#define UART_TX_PIN       1
#define UART_RX_PIN       3
#define UART_BAUD         115200

// Optional Local Buzzer (from previous constraint)
#define BUZZER_PIN        2

// STASIS Detection Logic & Thresholds
#define MOTION_THRESHOLD  15    // Grayscale delta
#define MOTION_RATIO      0.03  // 3% of pixels changed
#define TRACK_TIMEOUT     5000  // 5s to confirm face
#define DETECT_COOLDOWN   30000 // 30s cooldown after alert
#define BUZZ_DURATION     300   // Tone length
#define FACE_CONFIDENCE   0.72  // Minimum confidence to alert
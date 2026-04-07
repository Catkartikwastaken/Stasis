#pragma once

// =====================================================================
// STASIS Rover — ESP32-S3 Configuration
// =====================================================================

// ---- Motor Driver Pins (L298N / L293D) ----
// Motor A — Left Front
#define MOTOR_A_IN1   4
#define MOTOR_A_IN2   5
#define MOTOR_A_ENA   6

// Motor B — Left Rear
#define MOTOR_B_IN1   7
#define MOTOR_B_IN2   8
#define MOTOR_B_ENB   9

// Motor C — Right Front
#define MOTOR_C_IN1   10
#define MOTOR_C_IN2   11
#define MOTOR_C_ENA   12

// Motor D — Right Rear
#define MOTOR_D_IN1   13
#define MOTOR_D_IN2   14
#define MOTOR_D_ENB   15

// ---- Motor PWM Config ----
#define MOTOR_PWM_FREQ       5000
#define MOTOR_PWM_RESOLUTION 8
#define MOTOR_DEFAULT_SPEED  180   // 0-255
#define MOTOR_TURN_SPEED     140
#define MOTOR_REVERSE_SPEED  150

// ---- DS18B20 Temperature Sensor ----
#define TEMP_SENSOR_PIN   16
#define TEMP_READ_INTERVAL_MS 5000

// ---- GPS (NEO-6M via UART2) ----
#define GPS_RX_PIN   17
#define GPS_TX_PIN   18
#define GPS_BAUD     9600
#define GPS_CHECK_INTERVAL_MS 1000

// ---- Camera UART (ESP32-CAM via UART1) ----
#define CAM_RX_PIN   19
#define CAM_TX_PIN   20
#define CAM_BAUD     115200

// ---- MPU6050 (I2C) ----
#define IMU_SDA_PIN  21
#define IMU_SCL_PIN  22
#define IMU_ADDR     0x68
#define IMU_POLL_INTERVAL_MS 50   // 20 Hz

// ---- I2C LCD ----
#define LCD_ADDR       0x27
#define LCD_COLS       20
#define LCD_ROWS       4
#define LCD_ROTATE_MS  3000

// ---- Buzzer ----
#define BUZZER_PIN     2
#define BUZZER_CHANNEL 0

// ---- ESP-NOW ----
// Charging station ESP32-C3 Mini MAC address (update with actual)
#define STATION_MAC {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF}

// ---- Telemetry ----
#define TELEMETRY_INTERVAL_MS   2000

// ---- Navigation ----
#define MAX_GEOFENCE_POINTS     10
#define GEOFENCE_CHECK_MS       1000
#define WAYPOINT_REACH_RADIUS_M 2.0f
#define STATION_DOCK_RADIUS_M   2.0f
#define PATH_MATCH_RADIUS_M     10.0f

// ---- IMU Thresholds ----
#define STUCK_ACCEL_THRESHOLD   0.05f   // g
#define STUCK_DURATION_MS       3000
#define TILT_ANGLE_THRESHOLD    35.0f   // degrees
#define AUTO_REVERSE_TIMEOUT_MS 300000  // 5 minutes

// ---- Battery ----
#define BATTERY_ADC_PIN         35
#define BATTERY_LOW_VOLTAGE     3.6f
#define BATTERY_FULL_VOLTAGE    4.2f
#define BATTERY_DIVIDER_RATIO   2.0f   // voltage divider ratio

// ---- Detection ----
#define DETECTION_COOLDOWN_MS   30000
#define DETECTION_CONFIDENCE    0.72f

// ---- Rover States ----
enum RoverState : uint8_t {
    STATE_IDLE       = 0,
    STATE_NAVIGATING = 1,
    STATE_PATROLLING = 2,
    STATE_RETURNING  = 3,
    STATE_STUCK      = 4,
    STATE_CHARGING   = 5,
    STATE_EMERGENCY  = 6
};

// ---- ESP-NOW Packet Types ----
#define PKT_TELEMETRY  0x01
#define PKT_COMMAND    0x02
#define PKT_ALERT      0x03
#define PKT_IMAGE_CHUNK 0x04

// ---- Image Chunk Config ----
#define IMAGE_CHUNK_DATA_SIZE 240  // ESP-NOW max ~250 bytes minus header

// ---- Command Types ----
#define CMD_GOTO    1
#define CMD_STOP    2
#define CMD_RETURN  3
#define CMD_RESUME  4

// ---- Alert Types ----
#define ALERT_HUMAN       1
#define ALERT_STUCK       2
#define ALERT_LOW_BATTERY 3
#define ALERT_TILT        4

// ---- ESP-NOW Data Structures ----
#pragma pack(push, 1)

struct TelemetryPacket {
    uint8_t  packet_type;      // PKT_TELEMETRY
    float    gps_lat;
    float    gps_lon;
    float    temperature;
    float    battery_voltage;
    int16_t  accel_x;
    int16_t  accel_y;
    int16_t  accel_z;
    uint8_t  rover_state;
    uint8_t  is_charging;
};

struct CommandPacket {
    uint8_t  packet_type;      // PKT_COMMAND
    uint8_t  command;
    float    target_lat;
    float    target_lon;
    uint8_t  geofence_point_count;
    float    geofence_lats[MAX_GEOFENCE_POINTS];
    float    geofence_lons[MAX_GEOFENCE_POINTS];
};

struct AlertPacket {
    uint8_t  packet_type;      // PKT_ALERT
    uint8_t  alert_type;
    float    alert_lat;
    float    alert_lon;
    uint32_t timestamp;
    // NOTE: image data is NOT included here — ESP-NOW has a 250-byte
    // payload limit. Images are sent as separate IMAGE_CHUNK packets.
};

struct ImageChunkPacket {
    uint8_t  packet_type;      // PKT_IMAGE_CHUNK (0x04)
    uint8_t  is_first;         // 1 if first chunk
    uint8_t  is_last;          // 1 if final chunk
    char     data[IMAGE_CHUNK_DATA_SIZE];
};

#pragma pack(pop)

// ---- Firmware Info ----
#define FIRMWARE_VERSION "1.0.0"
#define DEVICE_NAME      "STASIS-ROVER-S3"

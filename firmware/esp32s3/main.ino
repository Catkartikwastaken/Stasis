/*
 * STASIS — Autonomous Forest Patrol Rover
 * ESP32-S3 Main Controller Firmware
 * Version 1.0.0
 */

#include "config.h"
#include "motor_controller.h"
#include "gps_handler.h"
#include "imu_handler.h"
#include "temp_sensor.h"
#include "path_memory.h"
#include "navigation.h"
#include "espnow_handler.h"
#include "camera_comms.h"
#include "lcd_display.h"
#include "alert_handler.h"
#include <esp_task_wdt.h>

// ---- Global Objects ----
MotorController motors;
GPSHandler gps;
IMUHandler imu;
TempSensor tempSensor;
PathMemory pathMemory;
Navigation nav;
ESPNowHandler espNow;
CameraComms camera;
LCDDisplay lcd;
AlertHandler alerts;

// ---- State Machine ----
volatile RoverState currentState = STATE_IDLE;
volatile RoverState previousState = STATE_IDLE;

// ---- Timers ----
unsigned long lastTelemetry = 0;
unsigned long lastIMUPoll = 0;
unsigned long lastGPSCheck = 0;
unsigned long lastTempRead = 0;
unsigned long stuckTimestamp = 0;
unsigned long autoReverseAttempted = 0;
bool reverseInProgress = false;
unsigned long reverseStart = 0;

// ---- Station coordinates (set via command) ----
volatile float stationLat = 0.0f;
volatile float stationLon = 0.0f;

// ---- Battery ----
float batteryVoltage = 4.2f;

// ---- Forward declarations ----
void handleCommand(const CommandPacket& cmd);
void changeState(RoverState newState);
void sendTelemetryPacket();
void handleStuckState();
void readBattery();

void setup() {
    Serial.begin(115200);
    Serial.println("\n=== STASIS Rover v" FIRMWARE_VERSION " ===");
    Serial.println("Initializing...");

    // Watchdog timer (30 seconds)
    esp_task_wdt_init(30, true);
    esp_task_wdt_add(NULL);

    // Initialize subsystems
    motors.begin();
    Serial.println("[OK] Motors");

    gps.begin();
    Serial.println("[OK] GPS");

    if (imu.begin()) {
        Serial.println("[OK] IMU (MPU6050)");
    } else {
        Serial.println("[!!] IMU init failed");
    }

    tempSensor.begin();
    Serial.println("[OK] Temperature Sensor");

    pathMemory.begin();
    Serial.println("[OK] Path Memory (NVS)");

    nav.begin(&motors, &gps, &pathMemory);
    Serial.println("[OK] Navigation");

    if (espNow.begin()) {
        Serial.println("[OK] ESP-NOW");
    } else {
        Serial.println("[!!] ESP-NOW init failed");
    }
    espNow.setCommandCallback(handleCommand);

    camera.begin();
    Serial.println("[OK] Camera UART");

    lcd.begin();
    Serial.println("[OK] LCD Display");

    alerts.begin();
    Serial.println("[OK] Alert Handler");

    // Battery pin
    pinMode(BATTERY_ADC_PIN, INPUT);
    analogSetAttenuation(ADC_11db);

    changeState(STATE_IDLE);
    Serial.println("=== Initialization Complete ===\n");
}

void loop() {
    esp_task_wdt_reset();

    unsigned long now = millis();

    // ---- GPS Update ----
    gps.update();

    // ---- IMU Update (20Hz) ----
    if (now - lastIMUPoll >= IMU_POLL_INTERVAL_MS) {
        lastIMUPoll = now;
        imu.setMotorCommandActive(motors.isMoving());
        imu.update();
    }

    // ---- Temperature Update ----
    tempSensor.update();

    // ---- Camera Detection ----
    camera.update();
    if (camera.hasNewDetection()) {
        CameraDetection det = camera.getDetection();
        if (det.confidence >= DETECTION_CONFIDENCE) {
            // Fire alert
            AlertPacket alertPkt;
            alertPkt.packet_type = PKT_ALERT;
            alertPkt.alert_type = ALERT_HUMAN;
            GPSData gd = gps.getData();
            alertPkt.alert_lat = gd.latitude;
            alertPkt.alert_lon = gd.longitude;
            alertPkt.timestamp = now;
            strncpy(alertPkt.image_b64, det.image_b64, sizeof(alertPkt.image_b64));
            espNow.sendAlert(alertPkt);

            alerts.humanDetected();
            lcd.showAlert("!! ALERT !!", "HUMAN DETECTED");

            Serial.printf("[ALERT] Human detected! Conf: %.2f\n", det.confidence);
        }
        camera.clearDetection();
    }

    // ---- Battery ----
    readBattery();

    // ---- Navigation Update ----
    nav.update();

    // ---- Alert Sound Update ----
    alerts.update();

    // ---- LCD Update ----
    GPSData gd = gps.getData();
    lcd.update(currentState, gd.latitude, gd.longitude,
               batteryVoltage, tempSensor.getTemperature(),
               espNow.isConnected(), true);

    // ---- State Machine ----
    switch (currentState) {
        case STATE_IDLE:
            // Waiting for commands
            break;

        case STATE_NAVIGATING:
            if (nav.hasReachedTarget()) {
                changeState(STATE_PATROLLING);
                nav.startPatrol();
            }
            // Check stuck/tilt
            if (imu.isStuck()) {
                changeState(STATE_STUCK);
            }
            if (imu.isTilted()) {
                changeState(STATE_STUCK);
            }
            break;

        case STATE_PATROLLING:
            // Navigation handles patrol waypoints
            if (imu.isStuck() || imu.isTilted()) {
                changeState(STATE_STUCK);
            }
            break;

        case STATE_RETURNING:
            if (nav.hasReachedTarget()) {
                changeState(STATE_CHARGING);
            }
            if (imu.isStuck() || imu.isTilted()) {
                changeState(STATE_STUCK);
            }
            break;

        case STATE_STUCK:
            handleStuckState();
            break;

        case STATE_CHARGING:
            // Waiting at station, monitored by station
            break;

        case STATE_EMERGENCY:
            // Full stop, wait for manual intervention
            break;
    }

    // ---- Low Battery Check ----
    if (batteryVoltage < BATTERY_LOW_VOLTAGE &&
        currentState != STATE_RETURNING &&
        currentState != STATE_CHARGING &&
        currentState != STATE_EMERGENCY) {
        AlertPacket alertPkt;
        alertPkt.packet_type = PKT_ALERT;
        alertPkt.alert_type = ALERT_LOW_BATTERY;
        GPSData gpsD = gps.getData();
        alertPkt.alert_lat = gpsD.latitude;
        alertPkt.alert_lon = gpsD.longitude;
        alertPkt.timestamp = now;
        alertPkt.image_b64[0] = '\0';
        espNow.sendAlert(alertPkt);
        alerts.lowBattery();

        if (stationLat != 0.0f || stationLon != 0.0f) {
            changeState(STATE_RETURNING);
            nav.returnToStation(stationLat, stationLon);
        }
    }

    // ---- Telemetry Broadcast ----
    if (now - lastTelemetry >= TELEMETRY_INTERVAL_MS) {
        lastTelemetry = now;
        sendTelemetryPacket();
    }
}

// ---- State Transition ----
void changeState(RoverState newState) {
    if (newState == currentState) return;
    previousState = currentState;
    currentState = newState;

    Serial.printf("[STATE] %d -> %d\n", previousState, newState);

    switch (newState) {
        case STATE_STUCK:
            motors.stop();
            stuckTimestamp = millis();
            reverseInProgress = false;
            if (imu.isTilted()) {
                alerts.tiltAlert();
                lcd.showAlert("!! STUCK !!", "TILT DETECTED");

                AlertPacket pkt;
                pkt.packet_type = PKT_ALERT;
                pkt.alert_type = ALERT_TILT;
                GPSData gd = gps.getData();
                pkt.alert_lat = gd.latitude;
                pkt.alert_lon = gd.longitude;
                pkt.timestamp = millis();
                pkt.image_b64[0] = '\0';
                espNow.sendAlert(pkt);
            } else {
                alerts.stuckAlert();
                lcd.showAlert("!! STUCK !!", "AWAITING CMD");

                AlertPacket pkt;
                pkt.packet_type = PKT_ALERT;
                pkt.alert_type = ALERT_STUCK;
                GPSData gd = gps.getData();
                pkt.alert_lat = gd.latitude;
                pkt.alert_lon = gd.longitude;
                pkt.timestamp = millis();
                pkt.image_b64[0] = '\0';
                espNow.sendAlert(pkt);
            }
            break;

        case STATE_IDLE:
        case STATE_CHARGING:
        case STATE_EMERGENCY:
            motors.stop();
            nav.stopNavigation();
            lcd.clearAlert();
            break;

        case STATE_PATROLLING:
        case STATE_NAVIGATING:
        case STATE_RETURNING:
            lcd.clearAlert();
            imu.resetFlags();
            break;
    }
}

// ---- Handle Stuck State ----
void handleStuckState() {
    unsigned long elapsed = millis() - stuckTimestamp;

    // Auto-reverse after 5 minutes with no commands
    if (elapsed >= AUTO_REVERSE_TIMEOUT_MS && !reverseInProgress) {
        reverseInProgress = true;
        reverseStart = millis();
        motors.backward();
        Serial.println("[STUCK] Auto-reverse attempt");
    }

    // Reverse for 3 seconds, then re-evaluate
    if (reverseInProgress && millis() - reverseStart > 3000) {
        motors.stop();
        reverseInProgress = false;
        imu.resetFlags();
        delay(500);
        imu.update();

        if (!imu.isStuck() && !imu.isTilted()) {
            Serial.println("[STUCK] Auto-reverse succeeded");
            changeState(previousState);
        } else {
            Serial.println("[STUCK] Still stuck after reverse");
            stuckTimestamp = millis();  // Reset wait timer
        }
    }
}

// ---- Send Telemetry ----
void sendTelemetryPacket() {
    GPSData gd = gps.getData();
    IMUData id = imu.getData();

    TelemetryPacket pkt;
    pkt.packet_type = PKT_TELEMETRY;
    pkt.gps_lat = gd.latitude;
    pkt.gps_lon = gd.longitude;
    pkt.temperature = tempSensor.getTemperature();
    pkt.battery_voltage = batteryVoltage;
    pkt.accel_x = (int16_t)(id.accel_x * 1000);
    pkt.accel_y = (int16_t)(id.accel_y * 1000);
    pkt.accel_z = (int16_t)(id.accel_z * 1000);
    pkt.rover_state = (uint8_t)currentState;
    pkt.is_charging = (currentState == STATE_CHARGING) ? 1 : 0;

    espNow.sendTelemetry(pkt);
}

// ---- Read Battery ----
void readBattery() {
    static unsigned long lastRead = 0;
    if (millis() - lastRead < 5000) return;
    lastRead = millis();

    int raw = analogRead(BATTERY_ADC_PIN);
    float voltage = (raw / 4095.0f) * 3.3f * BATTERY_DIVIDER_RATIO;
    // Simple exponential smoothing
    batteryVoltage = batteryVoltage * 0.9f + voltage * 0.1f;
}

// ---- Handle Incoming Commands ----
void handleCommand(const CommandPacket& cmd) {
    Serial.printf("[CMD] Received command: %d\n", cmd.command);

    switch (cmd.command) {
        case CMD_GOTO:
            // Update geofence if provided
            if (cmd.geofence_point_count > 0) {
                nav.setGeofence(cmd.geofence_lats, cmd.geofence_lons,
                                cmd.geofence_point_count);
            }
            nav.navigateTo(cmd.target_lat, cmd.target_lon);
            changeState(STATE_NAVIGATING);
            break;

        case CMD_STOP:
            changeState(STATE_EMERGENCY);
            break;

        case CMD_RETURN:
            stationLat = cmd.target_lat;
            stationLon = cmd.target_lon;
            nav.returnToStation(cmd.target_lat, cmd.target_lon);
            changeState(STATE_RETURNING);
            break;

        case CMD_RESUME:
            imu.resetFlags();
            lcd.clearAlert();
            if (previousState == STATE_PATROLLING) {
                changeState(STATE_PATROLLING);
                nav.startPatrol();
            } else if (previousState == STATE_NAVIGATING) {
                changeState(STATE_NAVIGATING);
            } else {
                changeState(STATE_IDLE);
            }
            break;
    }
}

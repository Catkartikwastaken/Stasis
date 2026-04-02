#pragma once
#include <Arduino.h>

struct IMUData {
    float accel_x = 0.0f;  // g
    float accel_y = 0.0f;
    float accel_z = 0.0f;
    float gyro_x  = 0.0f;  // deg/s
    float gyro_y  = 0.0f;
    float gyro_z  = 0.0f;
    float roll    = 0.0f;  // degrees
    float pitch   = 0.0f;
    float temperature = 0.0f;
};

class IMUHandler {
public:
    bool begin();
    void update();
    IMUData getData() const { return _data; }
    bool isStuck() const { return _stuck; }
    bool isTilted() const { return _tilted; }
    void resetFlags();

private:
    IMUData _data;
    bool _stuck   = false;
    bool _tilted  = false;
    unsigned long _lowAccelStart = 0;
    bool _motorCommandActive = false;

    void readRaw();
    void computeAngles();
    void checkStuck();
    void checkTilt();

    // For external motor state check
    friend class StasisRover;
public:
    void setMotorCommandActive(bool active) { _motorCommandActive = active; }
};

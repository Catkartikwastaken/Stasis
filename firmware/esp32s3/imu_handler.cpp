#include "imu_handler.h"
#include "config.h"
#include <Wire.h>

bool IMUHandler::begin() {
    Wire.begin(IMU_SDA_PIN, IMU_SCL_PIN);

    // Wake up MPU6050
    Wire.beginTransmission(IMU_ADDR);
    Wire.write(0x6B);  // PWR_MGMT_1
    Wire.write(0x00);  // Wake up
    if (Wire.endTransmission() != 0) {
        return false;
    }

    // Set accelerometer range to ±2g
    Wire.beginTransmission(IMU_ADDR);
    Wire.write(0x1C);
    Wire.write(0x00);
    Wire.endTransmission();

    // Set gyroscope range to ±250°/s
    Wire.beginTransmission(IMU_ADDR);
    Wire.write(0x1B);
    Wire.write(0x00);
    Wire.endTransmission();

    // Set DLPF for smoothing
    Wire.beginTransmission(IMU_ADDR);
    Wire.write(0x1A);
    Wire.write(0x06);  // ~5Hz bandwidth
    Wire.endTransmission();

    return true;
}

void IMUHandler::update() {
    readRaw();
    computeAngles();
    checkStuck();
    checkTilt();
}

void IMUHandler::readRaw() {
    Wire.beginTransmission(IMU_ADDR);
    Wire.write(0x3B);  // ACCEL_XOUT_H
    Wire.endTransmission(false);
    Wire.requestFrom((uint8_t)IMU_ADDR, (uint8_t)14, (uint8_t)true);

    if (Wire.available() >= 14) {
        int16_t ax = (Wire.read() << 8) | Wire.read();
        int16_t ay = (Wire.read() << 8) | Wire.read();
        int16_t az = (Wire.read() << 8) | Wire.read();
        int16_t temp_raw = (Wire.read() << 8) | Wire.read();
        int16_t gx = (Wire.read() << 8) | Wire.read();
        int16_t gy = (Wire.read() << 8) | Wire.read();
        int16_t gz = (Wire.read() << 8) | Wire.read();

        // Convert to g (±2g range = 16384 LSB/g)
        _data.accel_x = ax / 16384.0f;
        _data.accel_y = ay / 16384.0f;
        _data.accel_z = az / 16384.0f;

        // Convert to deg/s (±250°/s range = 131 LSB/°/s)
        _data.gyro_x = gx / 131.0f;
        _data.gyro_y = gy / 131.0f;
        _data.gyro_z = gz / 131.0f;

        // Temperature in Celsius
        _data.temperature = temp_raw / 340.0f + 36.53f;
    }
}

void IMUHandler::computeAngles() {
    _data.roll  = atan2(_data.accel_y, _data.accel_z) * 180.0f / PI;
    _data.pitch = atan2(-_data.accel_x,
                        sqrt(_data.accel_y * _data.accel_y +
                             _data.accel_z * _data.accel_z)) * 180.0f / PI;
}

void IMUHandler::checkStuck() {
    if (!_motorCommandActive) {
        _lowAccelStart = 0;
        return;
    }

    // Compute total linear acceleration magnitude (subtract gravity)
    float totalAccel = sqrt(_data.accel_x * _data.accel_x +
                            _data.accel_y * _data.accel_y +
                            _data.accel_z * _data.accel_z);
    float deviation = fabs(totalAccel - 1.0f);  // Deviation from 1g (stationary)

    if (deviation < STUCK_ACCEL_THRESHOLD) {
        if (_lowAccelStart == 0) {
            _lowAccelStart = millis();
        } else if (millis() - _lowAccelStart > STUCK_DURATION_MS) {
            _stuck = true;
        }
    } else {
        _lowAccelStart = 0;
        _stuck = false;
    }
}

void IMUHandler::checkTilt() {
    if (fabs(_data.roll) > TILT_ANGLE_THRESHOLD ||
        fabs(_data.pitch) > TILT_ANGLE_THRESHOLD) {
        _tilted = true;
    } else {
        _tilted = false;
    }
}

void IMUHandler::resetFlags() {
    _stuck = false;
    _tilted = false;
    _lowAccelStart = 0;
}

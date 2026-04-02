#pragma once
#include <Arduino.h>

class MotorController {
public:
    void begin();
    void forward(uint8_t speed = 0);
    void backward(uint8_t speed = 0);
    void turnLeft(uint8_t speed = 0);
    void turnRight(uint8_t speed = 0);
    void rotateLeft(uint8_t speed = 0);
    void rotateRight(uint8_t speed = 0);
    void stop();
    void setDefaultSpeed(uint8_t speed);
    uint8_t getDefaultSpeed() const { return _defaultSpeed; }
    bool isMoving() const { return _moving; }

private:
    void setMotor(uint8_t in1, uint8_t in2, uint8_t enPin, uint8_t enCh, int16_t speed);
    void setLeftMotors(int16_t speed);
    void setRightMotors(int16_t speed);
    uint8_t _defaultSpeed;
    bool _moving = false;
};

#include "motor_controller.h"
#include "config.h"

void MotorController::begin() {
    _defaultSpeed = MOTOR_DEFAULT_SPEED;
    _moving = false;

    // Configure motor pins as outputs
    uint8_t pins[] = {
        MOTOR_A_IN1, MOTOR_A_IN2,
        MOTOR_B_IN1, MOTOR_B_IN2,
        MOTOR_C_IN1, MOTOR_C_IN2,
        MOTOR_D_IN1, MOTOR_D_IN2
    };
    for (auto p : pins) {
        pinMode(p, OUTPUT);
        digitalWrite(p, LOW);
    }

    // Configure PWM channels for ENA/ENB pins
    ledcSetup(0, MOTOR_PWM_FREQ, MOTOR_PWM_RESOLUTION);
    ledcAttachPin(MOTOR_A_ENA, 0);

    ledcSetup(1, MOTOR_PWM_FREQ, MOTOR_PWM_RESOLUTION);
    ledcAttachPin(MOTOR_B_ENB, 1);

    ledcSetup(2, MOTOR_PWM_FREQ, MOTOR_PWM_RESOLUTION);
    ledcAttachPin(MOTOR_C_ENA, 2);

    ledcSetup(3, MOTOR_PWM_FREQ, MOTOR_PWM_RESOLUTION);
    ledcAttachPin(MOTOR_D_ENB, 3);

    stop();
}

void MotorController::setMotor(uint8_t in1, uint8_t in2, uint8_t enPin, uint8_t enCh, int16_t speed) {
    if (speed > 0) {
        digitalWrite(in1, HIGH);
        digitalWrite(in2, LOW);
    } else if (speed < 0) {
        digitalWrite(in1, LOW);
        digitalWrite(in2, HIGH);
        speed = -speed;
    } else {
        digitalWrite(in1, LOW);
        digitalWrite(in2, LOW);
    }
    ledcWrite(enCh, constrain(speed, 0, 255));
}

void MotorController::setLeftMotors(int16_t speed) {
    setMotor(MOTOR_A_IN1, MOTOR_A_IN2, MOTOR_A_ENA, 0, speed);  // Left Front
    setMotor(MOTOR_B_IN1, MOTOR_B_IN2, MOTOR_B_ENB, 1, speed);  // Left Rear
}

void MotorController::setRightMotors(int16_t speed) {
    setMotor(MOTOR_C_IN1, MOTOR_C_IN2, MOTOR_C_ENA, 2, speed);  // Right Front
    setMotor(MOTOR_D_IN1, MOTOR_D_IN2, MOTOR_D_ENB, 3, speed);  // Right Rear
}

void MotorController::forward(uint8_t speed) {
    uint8_t s = speed > 0 ? speed : _defaultSpeed;
    setLeftMotors(s);
    setRightMotors(s);
    _moving = true;
}

void MotorController::backward(uint8_t speed) {
    uint8_t s = speed > 0 ? speed : MOTOR_REVERSE_SPEED;
    setLeftMotors(-s);
    setRightMotors(-s);
    _moving = true;
}

void MotorController::turnLeft(uint8_t speed) {
    uint8_t s = speed > 0 ? speed : MOTOR_TURN_SPEED;
    setLeftMotors(s / 2);
    setRightMotors(s);
    _moving = true;
}

void MotorController::turnRight(uint8_t speed) {
    uint8_t s = speed > 0 ? speed : MOTOR_TURN_SPEED;
    setLeftMotors(s);
    setRightMotors(s / 2);
    _moving = true;
}

void MotorController::rotateLeft(uint8_t speed) {
    uint8_t s = speed > 0 ? speed : MOTOR_TURN_SPEED;
    setLeftMotors(-s);
    setRightMotors(s);
    _moving = true;
}

void MotorController::rotateRight(uint8_t speed) {
    uint8_t s = speed > 0 ? speed : MOTOR_TURN_SPEED;
    setLeftMotors(s);
    setRightMotors(-s);
    _moving = true;
}

void MotorController::stop() {
    setLeftMotors(0);
    setRightMotors(0);
    _moving = false;
}

void MotorController::setDefaultSpeed(uint8_t speed) {
    _defaultSpeed = constrain(speed, 0, 255);
}

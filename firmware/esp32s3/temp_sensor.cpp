#include "temp_sensor.h"
#include "config.h"

// Bit-bang OneWire for DS18B20 — no external library needed

void TempSensor::begin() {
    pinMode(TEMP_SENSOR_PIN, INPUT);
    _lastRead = 0;
    _ready = false;
    // Trigger initial conversion
    if (presence()) {
        writeByte(0xCC);  // Skip ROM
        writeByte(0x44);  // Start conversion
        _ready = true;
    }
}

void TempSensor::update() {
    if (millis() - _lastRead < TEMP_READ_INTERVAL_MS) return;
    _lastRead = millis();

    if (!presence()) {
        _ready = false;
        return;
    }

    writeByte(0xCC);  // Skip ROM
    writeByte(0xBE);  // Read scratchpad

    uint8_t lsb = readByte();
    uint8_t msb = readByte();

    // We only need the first 2 bytes
    // Reset to end reading
    presence();

    int16_t raw = (msb << 8) | lsb;
    _temperature = raw / 16.0f;
    _ready = true;

    // Start next conversion
    if (presence()) {
        writeByte(0xCC);
        writeByte(0x44);
    }
}

bool TempSensor::presence() {
    pinMode(TEMP_SENSOR_PIN, OUTPUT);
    digitalWrite(TEMP_SENSOR_PIN, LOW);
    delayMicroseconds(480);
    pinMode(TEMP_SENSOR_PIN, INPUT);
    delayMicroseconds(70);
    bool detected = !digitalRead(TEMP_SENSOR_PIN);
    delayMicroseconds(410);
    return detected;
}

void TempSensor::reset() {
    presence();
}

void TempSensor::writeBit(uint8_t bit) {
    pinMode(TEMP_SENSOR_PIN, OUTPUT);
    if (bit) {
        digitalWrite(TEMP_SENSOR_PIN, LOW);
        delayMicroseconds(6);
        pinMode(TEMP_SENSOR_PIN, INPUT);
        delayMicroseconds(64);
    } else {
        digitalWrite(TEMP_SENSOR_PIN, LOW);
        delayMicroseconds(60);
        pinMode(TEMP_SENSOR_PIN, INPUT);
        delayMicroseconds(10);
    }
}

uint8_t TempSensor::readBit() {
    pinMode(TEMP_SENSOR_PIN, OUTPUT);
    digitalWrite(TEMP_SENSOR_PIN, LOW);
    delayMicroseconds(6);
    pinMode(TEMP_SENSOR_PIN, INPUT);
    delayMicroseconds(9);
    uint8_t bit = digitalRead(TEMP_SENSOR_PIN);
    delayMicroseconds(55);
    return bit;
}

void TempSensor::writeByte(uint8_t data) {
    for (uint8_t i = 0; i < 8; i++) {
        writeBit(data & 0x01);
        data >>= 1;
    }
}

uint8_t TempSensor::readByte() {
    uint8_t data = 0;
    for (uint8_t i = 0; i < 8; i++) {
        data |= (readBit() << i);
    }
    return data;
}

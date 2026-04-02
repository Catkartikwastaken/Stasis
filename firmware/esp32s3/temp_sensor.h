#pragma once
#include <Arduino.h>

class TempSensor {
public:
    void begin();
    void update();
    float getTemperature() const { return _temperature; }
    bool isReady() const { return _ready; }

private:
    float _temperature = 0.0f;
    bool _ready = false;
    unsigned long _lastRead = 0;

    void reset();
    void writeBit(uint8_t bit);
    uint8_t readBit();
    void writeByte(uint8_t data);
    uint8_t readByte();
    bool presence();
};

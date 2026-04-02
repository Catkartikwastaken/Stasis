#pragma once
#include <Arduino.h>

class GPIOControl {
public:
    void begin();
    void setChargingRelay(bool enabled);
    bool isChargingEnabled() const { return _charging; }
    void triggerEmergencyStop();
    void clearEmergencyStop();

private:
    bool _charging = false;
};

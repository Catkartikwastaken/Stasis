#include "gpio_control.h"
#include "config.h"

void GPIOControl::begin() {
    pinMode(CHARGING_RELAY_PIN, OUTPUT);
    digitalWrite(CHARGING_RELAY_PIN, LOW);

    pinMode(EMERGENCY_STOP_PIN, OUTPUT);
    digitalWrite(EMERGENCY_STOP_PIN, LOW);

    _charging = false;
    Serial.println("[GPIO] Initialized");
}

void GPIOControl::setChargingRelay(bool enabled) {
    _charging = enabled;
    digitalWrite(CHARGING_RELAY_PIN, enabled ? HIGH : LOW);
    Serial.printf("[GPIO] Charging relay: %s\n", enabled ? "ON" : "OFF");
}

void GPIOControl::triggerEmergencyStop() {
    digitalWrite(EMERGENCY_STOP_PIN, HIGH);
    Serial.println("[GPIO] EMERGENCY STOP triggered");
}

void GPIOControl::clearEmergencyStop() {
    digitalWrite(EMERGENCY_STOP_PIN, LOW);
    Serial.println("[GPIO] Emergency stop cleared");
}

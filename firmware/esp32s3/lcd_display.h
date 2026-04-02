#pragma once
#include <Arduino.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include "config.h"

class LCDDisplay {
public:
    void begin();
    void update(RoverState state, float lat, float lon,
                float battery, float temp,
                bool signalOk, bool camActive);
    void showAlert(const char* line1, const char* line2);
    void clearAlert();

private:
    LiquidCrystal_I2C _lcd;
    uint8_t _currentScreen = 0;
    unsigned long _lastRotate = 0;
    bool _alertActive = false;
    char _alertLine1[21];
    char _alertLine2[21];

    void showScreen(uint8_t screen, RoverState state,
                    float lat, float lon,
                    float battery, float temp,
                    bool signalOk, bool camActive);
    const char* stateToString(RoverState state);

public:
    LCDDisplay() : _lcd(LCD_ADDR, LCD_COLS, LCD_ROWS) {}
};

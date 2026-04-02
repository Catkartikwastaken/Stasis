#include "lcd_display.h"

void LCDDisplay::begin() {
    _lcd.init();
    _lcd.backlight();
    _lcd.clear();
    _lcd.setCursor(0, 0);
    _lcd.print("  STASIS v1.0");
    _lcd.setCursor(0, 1);
    _lcd.print("  Initializing...");
    _currentScreen = 0;
    _lastRotate = millis();
    _alertActive = false;
}

void LCDDisplay::update(RoverState state, float lat, float lon,
                        float battery, float temp,
                        bool signalOk, bool camActive) {
    if (_alertActive) return;  // Alert has priority

    unsigned long now = millis();
    if (now - _lastRotate < LCD_ROTATE_MS) return;
    _lastRotate = now;

    _currentScreen = (_currentScreen + 1) % 4;
    showScreen(_currentScreen, state, lat, lon, battery, temp, signalOk, camActive);
}

void LCDDisplay::showScreen(uint8_t screen, RoverState state,
                            float lat, float lon,
                            float battery, float temp,
                            bool signalOk, bool camActive) {
    _lcd.clear();
    char buf[21];

    switch (screen) {
        case 0:  // State screen
            _lcd.setCursor(0, 0);
            _lcd.print("  STASIS v1.0");
            _lcd.setCursor(0, 1);
            snprintf(buf, sizeof(buf), " [%s]", stateToString(state));
            _lcd.print(buf);
            break;

        case 1:  // GPS screen
            _lcd.setCursor(0, 0);
            _lcd.print("GPS Coordinates:");
            _lcd.setCursor(0, 1);
            snprintf(buf, sizeof(buf), "%.4f,%.4f", lat, lon);
            _lcd.print(buf);
            break;

        case 2:  // Battery & temp
            _lcd.setCursor(0, 0);
            snprintf(buf, sizeof(buf), "Bat: %.1fV", battery);
            _lcd.print(buf);
            _lcd.setCursor(0, 1);
            snprintf(buf, sizeof(buf), "Temp: %.1f C", temp);
            _lcd.print(buf);
            break;

        case 3:  // Signal & camera
            _lcd.setCursor(0, 0);
            snprintf(buf, sizeof(buf), "SIGNAL: %s", signalOk ? "OK" : "WEAK");
            _lcd.print(buf);
            _lcd.setCursor(0, 1);
            snprintf(buf, sizeof(buf), "CAM: %s", camActive ? "ACTIVE" : "IDLE");
            _lcd.print(buf);
            break;
    }
}

void LCDDisplay::showAlert(const char* line1, const char* line2) {
    _alertActive = true;
    strncpy(_alertLine1, line1, 20);
    _alertLine1[20] = '\0';
    strncpy(_alertLine2, line2, 20);
    _alertLine2[20] = '\0';

    _lcd.clear();
    _lcd.setCursor(0, 0);
    _lcd.print(_alertLine1);
    _lcd.setCursor(0, 1);
    _lcd.print(_alertLine2);
}

void LCDDisplay::clearAlert() {
    _alertActive = false;
    _currentScreen = 0;
    _lastRotate = millis();
}

const char* LCDDisplay::stateToString(RoverState state) {
    switch (state) {
        case STATE_IDLE:       return "IDLE";
        case STATE_NAVIGATING: return "NAVIGATING";
        case STATE_PATROLLING: return "PATROLLING";
        case STATE_RETURNING:  return "RETURNING";
        case STATE_STUCK:      return "STUCK";
        case STATE_CHARGING:   return "CHARGING";
        case STATE_EMERGENCY:  return "EMERGENCY";
        default:               return "UNKNOWN";
    }
}

#pragma once
#include <Arduino.h>
#include "config.h"

class AlertHandler {
public:
    void begin();
    void humanDetected();
    void stuckAlert();
    void tiltAlert();
    void lowBattery();
    void chargingComplete();
    void update();  // Must be called in loop for non-blocking beeps
    void silence();

private:
    struct ToneStep {
        uint16_t freq;
        uint16_t durationMs;
        uint16_t pauseMs;
    };

    ToneStep _sequence[10];
    uint8_t  _seqLen = 0;
    uint8_t  _seqIdx = 0;
    bool     _playing = false;
    bool     _inPause = false;
    unsigned long _stepStart = 0;

    // Low battery periodic
    bool     _lowBatActive = false;
    unsigned long _lastLowBatBeep = 0;

    void startSequence(const ToneStep* steps, uint8_t count);
    void playTone(uint16_t freq);
    void stopTone();
};

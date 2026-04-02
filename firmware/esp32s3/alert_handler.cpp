#include "alert_handler.h"

void AlertHandler::begin() {
    ledcSetup(BUZZER_CHANNEL, 2000, 8);
    ledcAttachPin(BUZZER_PIN, BUZZER_CHANNEL);
    ledcWrite(BUZZER_CHANNEL, 0);
    _playing = false;
    _lowBatActive = false;
}

void AlertHandler::playTone(uint16_t freq) {
    ledcWriteTone(BUZZER_CHANNEL, freq);
    ledcWrite(BUZZER_CHANNEL, 128);  // 50% duty
}

void AlertHandler::stopTone() {
    ledcWrite(BUZZER_CHANNEL, 0);
}

void AlertHandler::startSequence(const ToneStep* steps, uint8_t count) {
    if (count > 10) count = 10;
    memcpy(_sequence, steps, count * sizeof(ToneStep));
    _seqLen = count;
    _seqIdx = 0;
    _playing = true;
    _inPause = false;
    _stepStart = millis();
    playTone(_sequence[0].freq);
}

void AlertHandler::humanDetected() {
    // 3 short beeps (100ms on, 100ms off) x3
    static const ToneStep seq[] = {
        {2500, 100, 100}, {2500, 100, 100}, {2500, 100, 100},
        {2500, 100, 100}, {2500, 100, 100}, {2500, 100, 100},
        {2500, 100, 100}, {2500, 100, 100}, {2500, 100, 300}
    };
    startSequence(seq, 9);
}

void AlertHandler::stuckAlert() {
    // 2 long beeps (500ms on, 200ms off) x2
    static const ToneStep seq[] = {
        {1500, 500, 200}, {1500, 500, 200},
        {1500, 500, 200}, {1500, 500, 200}
    };
    startSequence(seq, 4);
}

void AlertHandler::tiltAlert() {
    // Same as stuck
    stuckAlert();
}

void AlertHandler::lowBattery() {
    _lowBatActive = true;
    _lastLowBatBeep = 0;
}

void AlertHandler::chargingComplete() {
    // Ascending 3-tone melody
    static const ToneStep seq[] = {
        {1000, 200, 50}, {1500, 200, 50}, {2000, 400, 0}
    };
    startSequence(seq, 3);
    _lowBatActive = false;
}

void AlertHandler::silence() {
    stopTone();
    _playing = false;
    _lowBatActive = false;
}

void AlertHandler::update() {
    unsigned long now = millis();

    // Handle sequence playback
    if (_playing) {
        if (_inPause) {
            if (now - _stepStart >= _sequence[_seqIdx].pauseMs) {
                _seqIdx++;
                if (_seqIdx >= _seqLen) {
                    _playing = false;
                    stopTone();
                    return;
                }
                _inPause = false;
                _stepStart = now;
                playTone(_sequence[_seqIdx].freq);
            }
        } else {
            if (now - _stepStart >= _sequence[_seqIdx].durationMs) {
                stopTone();
                if (_sequence[_seqIdx].pauseMs > 0) {
                    _inPause = true;
                    _stepStart = now;
                } else {
                    _seqIdx++;
                    if (_seqIdx >= _seqLen) {
                        _playing = false;
                        return;
                    }
                    _stepStart = now;
                    playTone(_sequence[_seqIdx].freq);
                }
            }
        }
        return;
    }

    // Low battery periodic beep
    if (_lowBatActive && !_playing) {
        if (now - _lastLowBatBeep >= 10000) {
            _lastLowBatBeep = now;
            static const ToneStep seq[] = {{1200, 300, 0}};
            startSequence(seq, 1);
        }
    }
}

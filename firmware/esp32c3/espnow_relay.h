#pragma once
#include <Arduino.h>
#include <esp_now.h>

typedef void (*TelemetryCallback)(const uint8_t* data, size_t len);
typedef void (*AlertCallback)(const uint8_t* data, size_t len);

class ESPNowRelay {
public:
    bool begin();
    void sendCommandToRover(const uint8_t* data, size_t len);
    void setTelemetryCallback(TelemetryCallback cb);
    void setAlertCallback(AlertCallback cb);
    bool isRoverConnected() const;
    unsigned long lastRoverContact() const { return _lastRx; }

    static void onDataRecv(const uint8_t* mac, const uint8_t* data, int len);
    static void onDataSent(const uint8_t* mac, esp_now_send_status_t status);

private:
    static ESPNowRelay* _instance;
    static TelemetryCallback _telemetryCb;
    static AlertCallback _alertCb;
    unsigned long _lastRx = 0;
    bool _sendOk = false;
};

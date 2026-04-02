#pragma once
#include <Arduino.h>
#include "config.h"

typedef void (*CommandCallback)(const CommandPacket& cmd);

class ESPNowHandler {
public:
    bool begin();
    void sendTelemetry(const TelemetryPacket& pkt);
    void sendAlert(const AlertPacket& pkt);
    void setCommandCallback(CommandCallback cb);
    bool isConnected() const { return _connected; }
    unsigned long lastReceiveTime() const { return _lastRxTime; }

    // Static callbacks for ESP-NOW
    static void onDataSent(const uint8_t* mac, esp_now_send_status_t status);
    static void onDataRecv(const uint8_t* mac, const uint8_t* data, int len);

private:
    bool _connected = false;
    unsigned long _lastRxTime = 0;
    static ESPNowHandler* _instance;
    static CommandCallback _cmdCallback;
};

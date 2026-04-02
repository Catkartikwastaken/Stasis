#pragma once
#include <Arduino.h>
#include <WiFi.h>

class WiFiBridge {
public:
    bool begin();
    bool isConnected() const;
    IPAddress getIP() const;
    String getMode() const;
    uint8_t getClientCount() const;

private:
    bool _apMode = true;
    bool setupAP();
    bool setupSTA();
};

#pragma once
#include <Arduino.h>
#include <WiFiServer.h>
#include <WiFiClient.h>

class UARTPiBridge {
public:
    void begin();
    void update();
    bool hasPiData() const { return _piDataReady; }
    String readPiLine();
    void sendToPi(const String& data);

private:
    WiFiServer* _tcpServer = nullptr;
    WiFiClient _clients[4];
    uint8_t _clientCount = 0;
    String _piRxBuffer;
    bool _piDataReady = false;

    void handleTCPClients();
    void relayTCPtoUART();
    void relayUARTtoTCP();
};

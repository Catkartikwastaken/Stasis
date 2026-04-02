#include "uart_pi_bridge.h"
#include "config.h"

void UARTPiBridge::begin() {
    Serial1.begin(PI_UART_BAUD, SERIAL_8N1, PI_UART_RX, PI_UART_TX);
    _piRxBuffer.reserve(TCP_BUFFER_SIZE);

    _tcpServer = new WiFiServer(TCP_SERVER_PORT);
    _tcpServer->begin();
    _tcpServer->setNoDelay(true);

    Serial.printf("[BRIDGE] TCP server on port %d, UART at %d baud\n",
                  TCP_SERVER_PORT, PI_UART_BAUD);
}

void UARTPiBridge::update() {
    handleTCPClients();
    relayTCPtoUART();
    relayUARTtoTCP();
}

void UARTPiBridge::handleTCPClients() {
    // Accept new clients
    if (_tcpServer->hasClient()) {
        WiFiClient newClient = _tcpServer->available();
        bool placed = false;
        for (int i = 0; i < 4; i++) {
            if (!_clients[i] || !_clients[i].connected()) {
                _clients[i] = newClient;
                placed = true;
                Serial.printf("[BRIDGE] Client %d connected\n", i);
                break;
            }
        }
        if (!placed) {
            newClient.stop();
            Serial.println("[BRIDGE] Max clients reached, rejected");
        }
    }
}

void UARTPiBridge::relayTCPtoUART() {
    // Read from WiFi clients and send to Pi via UART
    for (int i = 0; i < 4; i++) {
        if (_clients[i] && _clients[i].connected() && _clients[i].available()) {
            while (_clients[i].available()) {
                uint8_t buf[256];
                size_t len = _clients[i].read(buf, sizeof(buf));
                if (len > 0) {
                    Serial1.write(buf, len);
                }
            }
        }
    }
}

void UARTPiBridge::relayUARTtoTCP() {
    // Read from Pi UART and relay to all connected WiFi clients
    while (Serial1.available()) {
        char c = Serial1.read();
        _piRxBuffer += c;

        if (c == '\n') {
            _piDataReady = true;
            // Send to all connected TCP clients
            for (int i = 0; i < 4; i++) {
                if (_clients[i] && _clients[i].connected()) {
                    _clients[i].print(_piRxBuffer);
                }
            }
        }
    }
}

String UARTPiBridge::readPiLine() {
    String line = _piRxBuffer;
    _piRxBuffer = "";
    _piDataReady = false;
    return line;
}

void UARTPiBridge::sendToPi(const String& data) {
    Serial1.println(data);
    Serial1.flush();
}

#pragma once
#include <Arduino.h>

struct GPSData {
    float latitude  = 0.0f;
    float longitude = 0.0f;
    float altitude  = 0.0f;
    float speed_knots = 0.0f;
    float course    = 0.0f;
    uint8_t satellites = 0;
    bool  fix       = false;
    uint32_t lastFixTime = 0;
};

class GPSHandler {
public:
    void begin();
    void update();
    GPSData getData() const { return _data; }
    bool hasFix() const { return _data.fix; }
    float distanceTo(float lat, float lon) const;
    float bearingTo(float lat, float lon) const;
    static float distanceBetween(float lat1, float lon1, float lat2, float lon2);
    static float bearingBetween(float lat1, float lon1, float lat2, float lon2);

private:
    GPSData _data;
    void parseNMEA(const String& sentence);
    void parseGGA(const String& sentence);
    void parseRMC(const String& sentence);
    float parseCoord(const String& coord, const String& dir);
    String _buffer;
};

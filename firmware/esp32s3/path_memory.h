#pragma once
#include <Arduino.h>
#include <Preferences.h>

struct Waypoint {
    float lat;
    float lon;
};

class PathMemory {
public:
    void begin();
    bool hasPath(const char* geohash);
    bool loadPath(const char* geohash, Waypoint* waypoints, uint8_t& count);
    bool savePath(const char* geohash, const Waypoint* waypoints, uint8_t count);
    bool deletePath(const char* geohash);
    static void latLonToGeohash(float lat, float lon, char* hash, uint8_t precision = 6);

    static const uint8_t MAX_PATH_WAYPOINTS = 50;

private:
    Preferences _prefs;
};

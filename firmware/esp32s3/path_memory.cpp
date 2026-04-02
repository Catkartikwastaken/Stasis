#include "path_memory.h"
#include "config.h"
#include <ArduinoJson.h>

void PathMemory::begin() {
    _prefs.begin("stasis_paths", false);
}

void PathMemory::latLonToGeohash(float lat, float lon, char* hash, uint8_t precision) {
    // Simple geohash encoding
    const char base32[] = "0123456789bcdefghjkmnpqrstuvwxyz";
    float latRange[2] = {-90.0f, 90.0f};
    float lonRange[2] = {-180.0f, 180.0f};
    bool isLon = true;
    int bit = 0;
    int idx = 0;
    uint8_t ch = 0;

    while (idx < precision) {
        float mid;
        if (isLon) {
            mid = (lonRange[0] + lonRange[1]) / 2.0f;
            if (lon >= mid) {
                ch |= (1 << (4 - bit));
                lonRange[0] = mid;
            } else {
                lonRange[1] = mid;
            }
        } else {
            mid = (latRange[0] + latRange[1]) / 2.0f;
            if (lat >= mid) {
                ch |= (1 << (4 - bit));
                latRange[0] = mid;
            } else {
                latRange[1] = mid;
            }
        }
        isLon = !isLon;
        bit++;
        if (bit == 5) {
            hash[idx++] = base32[ch];
            ch = 0;
            bit = 0;
        }
    }
    hash[idx] = '\0';
}

bool PathMemory::hasPath(const char* geohash) {
    char key[16];
    snprintf(key, sizeof(key), "p_%s", geohash);
    return _prefs.isKey(key);
}

bool PathMemory::loadPath(const char* geohash, Waypoint* waypoints, uint8_t& count) {
    char key[16];
    snprintf(key, sizeof(key), "p_%s", geohash);

    String json = _prefs.getString(key, "");
    if (json.length() == 0) return false;

    StaticJsonDocument<2048> doc;
    DeserializationError err = deserializeJson(doc, json);
    if (err) return false;

    JsonArray arr = doc.as<JsonArray>();
    count = 0;
    for (JsonObject wp : arr) {
        if (count >= MAX_PATH_WAYPOINTS) break;
        waypoints[count].lat = wp["la"].as<float>();
        waypoints[count].lon = wp["lo"].as<float>();
        count++;
    }
    return count > 0;
}

bool PathMemory::savePath(const char* geohash, const Waypoint* waypoints, uint8_t count) {
    if (count == 0 || count > MAX_PATH_WAYPOINTS) return false;

    char key[16];
    snprintf(key, sizeof(key), "p_%s", geohash);

    StaticJsonDocument<2048> doc;
    JsonArray arr = doc.to<JsonArray>();
    for (uint8_t i = 0; i < count; i++) {
        JsonObject wp = arr.createNestedObject();
        wp["la"] = waypoints[i].lat;
        wp["lo"] = waypoints[i].lon;
    }

    String json;
    serializeJson(doc, json);
    return _prefs.putString(key, json) > 0;
}

bool PathMemory::deletePath(const char* geohash) {
    char key[16];
    snprintf(key, sizeof(key), "p_%s", geohash);
    return _prefs.remove(key);
}

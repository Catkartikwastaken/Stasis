#include "gps_handler.h"
#include "config.h"

void GPSHandler::begin() {
    Serial2.begin(GPS_BAUD, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN);
    _buffer.reserve(128);
}

void GPSHandler::update() {
    while (Serial2.available()) {
        char c = Serial2.read();
        if (c == '\n') {
            _buffer.trim();
            if (_buffer.startsWith("$")) {
                parseNMEA(_buffer);
            }
            _buffer = "";
        } else if (c != '\r') {
            _buffer += c;
        }
    }
}

void GPSHandler::parseNMEA(const String& sentence) {
    if (sentence.startsWith("$GPGGA") || sentence.startsWith("$GNGGA")) {
        parseGGA(sentence);
    } else if (sentence.startsWith("$GPRMC") || sentence.startsWith("$GNRMC")) {
        parseRMC(sentence);
    }
}

void GPSHandler::parseGGA(const String& sentence) {
    // $GPGGA,time,lat,N/S,lon,E/W,quality,numSV,hdop,alt,M,sep,M,diffAge,diffStation*cs
    int idx = 0;
    String parts[15];
    int start = 0;
    for (int i = 0; i < (int)sentence.length() && idx < 15; i++) {
        if (sentence[i] == ',' || sentence[i] == '*') {
            parts[idx++] = sentence.substring(start, i);
            start = i + 1;
        }
    }
    if (idx >= 10) {
        if (parts[6].toInt() > 0) {
            _data.latitude  = parseCoord(parts[2], parts[3]);
            _data.longitude = parseCoord(parts[4], parts[5]);
            _data.satellites = parts[7].toInt();
            _data.altitude  = parts[9].toFloat();
            _data.fix = true;
            _data.lastFixTime = millis();
        } else {
            _data.fix = false;
        }
    }
}

void GPSHandler::parseRMC(const String& sentence) {
    // $GPRMC,time,status,lat,N/S,lon,E/W,spd,cog,date,mv,mvE,posMode*cs
    int idx = 0;
    String parts[13];
    int start = 0;
    for (int i = 0; i < (int)sentence.length() && idx < 13; i++) {
        if (sentence[i] == ',' || sentence[i] == '*') {
            parts[idx++] = sentence.substring(start, i);
            start = i + 1;
        }
    }
    if (idx >= 8) {
        if (parts[2] == "A") {
            _data.latitude   = parseCoord(parts[3], parts[4]);
            _data.longitude  = parseCoord(parts[5], parts[6]);
            _data.speed_knots = parts[7].toFloat();
            if (parts[8].length() > 0) {
                _data.course = parts[8].toFloat();
            }
            _data.fix = true;
            _data.lastFixTime = millis();
        } else {
            _data.fix = false;
        }
    }
}

float GPSHandler::parseCoord(const String& coord, const String& dir) {
    if (coord.length() == 0) return 0.0f;
    int dotPos = coord.indexOf('.');
    if (dotPos < 2) return 0.0f;

    float degrees = coord.substring(0, dotPos - 2).toFloat();
    float minutes = coord.substring(dotPos - 2).toFloat();
    float result = degrees + minutes / 60.0f;

    if (dir == "S" || dir == "W") result = -result;
    return result;
}

float GPSHandler::distanceTo(float lat, float lon) const {
    return distanceBetween(_data.latitude, _data.longitude, lat, lon);
}

float GPSHandler::bearingTo(float lat, float lon) const {
    return bearingBetween(_data.latitude, _data.longitude, lat, lon);
}

float GPSHandler::distanceBetween(float lat1, float lon1, float lat2, float lon2) {
    // Haversine formula — returns meters
    const float R = 6371000.0f;
    float dLat = radians(lat2 - lat1);
    float dLon = radians(lon2 - lon1);
    float a = sin(dLat / 2) * sin(dLat / 2) +
              cos(radians(lat1)) * cos(radians(lat2)) *
              sin(dLon / 2) * sin(dLon / 2);
    float c = 2 * atan2(sqrt(a), sqrt(1 - a));
    return R * c;
}

float GPSHandler::bearingBetween(float lat1, float lon1, float lat2, float lon2) {
    float dLon = radians(lon2 - lon1);
    float y = sin(dLon) * cos(radians(lat2));
    float x = cos(radians(lat1)) * sin(radians(lat2)) -
              sin(radians(lat1)) * cos(radians(lat2)) * cos(dLon);
    float bearing = degrees(atan2(y, x));
    return fmod(bearing + 360.0f, 360.0f);
}

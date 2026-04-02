#include "navigation.h"

void Navigation::begin(MotorController* motors, GPSHandler* gps, PathMemory* pathMem) {
    _motors = motors;
    _gps = gps;
    _pathMem = pathMem;
    _navigating = false;
    _patrolling = false;
    _reachedTarget = false;
}

void Navigation::setGeofence(const float* lats, const float* lons, uint8_t count) {
    _geofenceCount = min(count, (uint8_t)MAX_GEOFENCE_POINTS);
    for (uint8_t i = 0; i < _geofenceCount; i++) {
        _geofenceLats[i] = lats[i];
        _geofenceLons[i] = lons[i];
    }
}

bool Navigation::isInsideGeofence(float lat, float lon) const {
    if (_geofenceCount < 3) return true;  // No valid geofence

    // Ray casting algorithm
    bool inside = false;
    int j = _geofenceCount - 1;
    for (int i = 0; i < _geofenceCount; i++) {
        if (((_geofenceLons[i] > lon) != (_geofenceLons[j] > lon)) &&
            (lat < (_geofenceLats[j] - _geofenceLats[i]) *
             (lon - _geofenceLons[i]) /
             (_geofenceLons[j] - _geofenceLons[i]) + _geofenceLats[i])) {
            inside = !inside;
        }
        j = i;
    }
    return inside;
}

void Navigation::navigateTo(float lat, float lon) {
    _targetLat = lat;
    _targetLon = lon;
    _navigating = true;
    _reachedTarget = false;

    // Check if we have a stored path
    char geohash[8];
    PathMemory::latLonToGeohash(lat, lon, geohash, 6);
    if (_pathMem->hasPath(geohash)) {
        if (_pathMem->loadPath(geohash, _currentPath, _pathCount)) {
            _pathIndex = 0;
            _followingStoredPath = true;
            _recording = false;
            return;
        }
    }

    // No stored path — navigate directly and record
    _followingStoredPath = false;
    _recording = true;
    _recordedCount = 0;
    _lastRecordTime = millis();
}

void Navigation::startPatrol() {
    _patrolling = true;
    selectNextPatrolPoint();
}

void Navigation::stopNavigation() {
    _navigating = false;
    _patrolling = false;
    _recording = false;
    _followingStoredPath = false;
    _motors->stop();
}

void Navigation::returnToStation(float stationLat, float stationLon) {
    _patrolling = false;
    navigateTo(stationLat, stationLon);
}

float Navigation::getDistanceToTarget() const {
    if (!_gps->hasFix()) return -1.0f;
    GPSData d = _gps->getData();
    return GPSHandler::distanceBetween(d.latitude, d.longitude, _targetLat, _targetLon);
}

void Navigation::update() {
    if (!_navigating || !_gps->hasFix()) return;

    unsigned long now = millis();
    if (now - _lastNavUpdate < 200) return;  // 5Hz update
    _lastNavUpdate = now;

    GPSData pos = _gps->getData();

    // Geofence check every second
    if (now - _lastGeofenceCheck > GEOFENCE_CHECK_MS) {
        _lastGeofenceCheck = now;
        _outsideGeofence = !isInsideGeofence(pos.latitude, pos.longitude);
        if (_outsideGeofence && _geofenceCount >= 3) {
            // Navigate to nearest geofence boundary point
            float nearLat, nearLon;
            getNearestGeofencePoint(pos.latitude, pos.longitude, nearLat, nearLon);
            _targetLat = nearLat;
            _targetLon = nearLon;
            _followingStoredPath = false;
            _recording = false;
        }
    }

    // Following stored path
    if (_followingStoredPath && _pathIndex < _pathCount) {
        float dist = GPSHandler::distanceBetween(
            pos.latitude, pos.longitude,
            _currentPath[_pathIndex].lat, _currentPath[_pathIndex].lon);

        if (dist < WAYPOINT_REACH_RADIUS_M) {
            _pathIndex++;
            if (_pathIndex >= _pathCount) {
                // Reached end of stored path
                _reachedTarget = true;
                _followingStoredPath = false;
                _motors->stop();
                if (_patrolling) selectNextPatrolPoint();
                return;
            }
        }
        float bearing = GPSHandler::bearingBetween(
            pos.latitude, pos.longitude,
            _currentPath[_pathIndex].lat, _currentPath[_pathIndex].lon);
        steerToward(bearing);
        return;
    }

    // Direct navigation
    float dist = GPSHandler::distanceBetween(
        pos.latitude, pos.longitude, _targetLat, _targetLon);

    if (dist < WAYPOINT_REACH_RADIUS_M) {
        _reachedTarget = true;
        _navigating = false;
        _motors->stop();

        // Save recorded path
        if (_recording && _recordedCount > 1) {
            char geohash[8];
            PathMemory::latLonToGeohash(_targetLat, _targetLon, geohash, 6);
            _pathMem->savePath(geohash, _recordedPath, _recordedCount);
            _recording = false;
        }

        if (_patrolling) selectNextPatrolPoint();
        return;
    }

    // Record waypoints
    if (_recording) {
        recordWaypoint();
    }

    float bearing = GPSHandler::bearingBetween(
        pos.latitude, pos.longitude, _targetLat, _targetLon);
    steerToward(bearing);
}

void Navigation::steerToward(float bearing) {
    GPSData pos = _gps->getData();
    float heading = pos.course;

    // Calculate angle difference
    float diff = bearing - heading;
    while (diff > 180.0f) diff -= 360.0f;
    while (diff < -180.0f) diff += 360.0f;

    if (fabs(diff) < 10.0f) {
        _motors->forward();
    } else if (diff > 0) {
        if (diff > 45.0f) {
            _motors->rotateRight();
        } else {
            _motors->turnRight();
        }
    } else {
        if (diff < -45.0f) {
            _motors->rotateLeft();
        } else {
            _motors->turnLeft();
        }
    }
}

float Navigation::getNearestGeofencePoint(float lat, float lon, float& nearLat, float& nearLon) const {
    float minDist = 999999.0f;
    nearLat = _geofenceLats[0];
    nearLon = _geofenceLons[0];

    for (uint8_t i = 0; i < _geofenceCount; i++) {
        // Check midpoints of edges too
        uint8_t j = (i + 1) % _geofenceCount;
        float midLat = (_geofenceLats[i] + _geofenceLats[j]) / 2.0f;
        float midLon = (_geofenceLons[i] + _geofenceLons[j]) / 2.0f;

        float d1 = GPSHandler::distanceBetween(lat, lon, _geofenceLats[i], _geofenceLons[i]);
        float d2 = GPSHandler::distanceBetween(lat, lon, midLat, midLon);

        if (d1 < minDist) {
            minDist = d1;
            nearLat = _geofenceLats[i];
            nearLon = _geofenceLons[i];
        }
        if (d2 < minDist) {
            minDist = d2;
            nearLat = midLat;
            nearLon = midLon;
        }
    }
    return minDist;
}

void Navigation::selectNextPatrolPoint() {
    if (_geofenceCount < 3) return;

    // Select a random interior point within the geofence polygon
    // Use centroid with random offset
    float centLat = 0, centLon = 0;
    for (uint8_t i = 0; i < _geofenceCount; i++) {
        centLat += _geofenceLats[i];
        centLon += _geofenceLons[i];
    }
    centLat /= _geofenceCount;
    centLon /= _geofenceCount;

    // Try random points around centroid
    for (int attempt = 0; attempt < 10; attempt++) {
        float offsetLat = (random(-1000, 1000) / 100000.0f);
        float offsetLon = (random(-1000, 1000) / 100000.0f);
        float tryLat = centLat + offsetLat;
        float tryLon = centLon + offsetLon;

        if (isInsideGeofence(tryLat, tryLon)) {
            navigateTo(tryLat, tryLon);
            return;
        }
    }

    // Fallback: navigate toward centroid
    navigateTo(centLat, centLon);
}

void Navigation::recordWaypoint() {
    if (_recordedCount >= PathMemory::MAX_PATH_WAYPOINTS) return;

    unsigned long now = millis();
    if (now - _lastRecordTime < 2000) return;  // Record every 2s
    _lastRecordTime = now;

    GPSData pos = _gps->getData();
    _recordedPath[_recordedCount].lat = pos.latitude;
    _recordedPath[_recordedCount].lon = pos.longitude;
    _recordedCount++;
}

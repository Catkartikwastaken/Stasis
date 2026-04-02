#pragma once
#include <Arduino.h>
#include "gps_handler.h"
#include "motor_controller.h"
#include "path_memory.h"
#include "config.h"

class Navigation {
public:
    void begin(MotorController* motors, GPSHandler* gps, PathMemory* pathMem);
    void update();

    void setGeofence(const float* lats, const float* lons, uint8_t count);
    bool isInsideGeofence(float lat, float lon) const;

    void navigateTo(float lat, float lon);
    void startPatrol();
    void stopNavigation();
    void returnToStation(float stationLat, float stationLon);

    bool hasReachedTarget() const { return _reachedTarget; }
    bool isOutsideGeofence() const { return _outsideGeofence; }
    float getTargetLat() const { return _targetLat; }
    float getTargetLon() const { return _targetLon; }
    float getDistanceToTarget() const;

private:
    MotorController* _motors = nullptr;
    GPSHandler* _gps = nullptr;
    PathMemory* _pathMem = nullptr;

    float _geofenceLats[MAX_GEOFENCE_POINTS];
    float _geofenceLons[MAX_GEOFENCE_POINTS];
    uint8_t _geofenceCount = 0;

    float _targetLat = 0, _targetLon = 0;
    bool _navigating = false;
    bool _patrolling = false;
    bool _reachedTarget = false;
    bool _outsideGeofence = false;

    // Stored path following
    Waypoint _currentPath[PathMemory::MAX_PATH_WAYPOINTS];
    uint8_t _pathCount = 0;
    uint8_t _pathIndex = 0;
    bool _followingStoredPath = false;

    // Path recording
    Waypoint _recordedPath[PathMemory::MAX_PATH_WAYPOINTS];
    uint8_t _recordedCount = 0;
    bool _recording = false;
    unsigned long _lastRecordTime = 0;

    unsigned long _lastNavUpdate = 0;
    unsigned long _lastGeofenceCheck = 0;

    void steerToward(float bearing);
    float getNearestGeofencePoint(float lat, float lon, float& nearLat, float& nearLon) const;
    void selectNextPatrolPoint();
    void recordWaypoint();
};

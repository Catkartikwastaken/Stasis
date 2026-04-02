"""
STASIS Server — Telemetry Handler
Process and store rover telemetry data.
"""
from database import Database


class TelemetryHandler:
    def __init__(self, db: Database):
        self._db = db
        self._latest = {}

    def process(self, data):
        """Process incoming telemetry data and store in database."""
        self._latest = {
            "lat": data.get("lat", 0),
            "lon": data.get("lon", 0),
            "battery": data.get("battery", 0),
            "temp": data.get("temp", 0),
            "accel_x": data.get("accel_x", 0),
            "accel_y": data.get("accel_y", 0),
            "accel_z": data.get("accel_z", 0),
            "state": data.get("state", 0),
            "charging": data.get("charging", 0),
            "timestamp": data.get("timestamp", 0)
        }
        self._db.insert_telemetry(self._latest)

    def get_latest(self):
        """Return the latest telemetry snapshot."""
        return self._latest

    def get_history(self, limit=100):
        """Return telemetry history."""
        return self._db.get_telemetry(limit)

    def get_status(self):
        """Return rover health snapshot."""
        from config import ROVER_STATES, BATTERY_LOW_VOLTAGE
        state_code = self._latest.get("state", 0)
        battery = self._latest.get("battery", 0)
        return {
            "connected": bool(self._latest),
            "state": ROVER_STATES.get(state_code, "UNKNOWN"),
            "state_code": state_code,
            "lat": self._latest.get("lat", 0),
            "lon": self._latest.get("lon", 0),
            "battery_voltage": battery,
            "battery_percent": max(0, min(100, int((battery - 3.3) / (4.2 - 3.3) * 100))),
            "temperature": self._latest.get("temp", 0),
            "is_charging": self._latest.get("charging", 0),
            "battery_low": battery < BATTERY_LOW_VOLTAGE if battery > 0 else False
        }

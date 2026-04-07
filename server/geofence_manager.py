"""
STASIS Server — Geofence Manager
Store and serve geofence configurations.
"""
import json
from database import Database


class GeofenceManager:
    def __init__(self, db: Database):
        self._db = db

    def get_all(self):
        """Get all geofence configurations."""
        geofences = self._db.get_geofences()
        for gf in geofences:
            if isinstance(gf.get("polygon_json"), str):
                gf["polygon"] = json.loads(gf["polygon_json"])
            else:
                gf["polygon"] = gf.get("polygon_json", [])
        return geofences

    def create(self, name, polygon):
        """Create a new geofence."""
        return self._db.create_geofence(name, polygon)

    def update(self, gf_id, name=None, polygon=None, active=None):
        """Update an existing geofence."""
        self._db.update_geofence(gf_id, name, polygon, active)

    def delete(self, gf_id):
        """Delete a geofence."""
        self._db.delete_geofence(gf_id)

    def activate(self, gf_id):
        """Deactivate all geofences and activate the specified one."""
        conn = self._db._get_conn()
        conn.execute("UPDATE geofences SET active = 0")
        conn.execute("UPDATE geofences SET active = 1 WHERE id = ?", (gf_id,))
        conn.commit()

    def get_active(self):
        """Get the currently active geofence."""
        gf = self._db.get_active_geofence()
        if gf and isinstance(gf.get("polygon_json"), str):
            gf["polygon"] = json.loads(gf["polygon_json"])
        return gf

    def get_active_polygon_arrays(self):
        """Get active geofence as separate lat/lon arrays for ESP-NOW."""
        gf = self.get_active()
        if not gf or not gf.get("polygon"):
            return [], []
        lats = [p.get("lat", p[0] if isinstance(p, list) else 0)
                for p in gf["polygon"]]
        lons = [p.get("lon", p[1] if isinstance(p, list) else 0)
                for p in gf["polygon"]]
        return lats, lons

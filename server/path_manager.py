"""
STASIS Server — Path Manager
Store and serve learned patrol paths.
"""
import json
from database import Database


class PathManager:
    def __init__(self, db: Database):
        self._db = db

    def save_path(self, location_hash, waypoints):
        """Save a learned path."""
        self._db.save_path(location_hash, waypoints)

    def get_all_paths(self):
        """Get all stored paths."""
        paths = self._db.get_paths()
        for p in paths:
            if isinstance(p.get("waypoints_json"), str):
                p["waypoints"] = json.loads(p["waypoints_json"])
            else:
                p["waypoints"] = p.get("waypoints_json", [])
        return paths

    def get_path_count(self):
        """Get total number of stored paths."""
        return len(self._db.get_paths())

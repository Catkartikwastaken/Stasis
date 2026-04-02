"""
STASIS Server — Alert Handler
Handle, persist, and serve detection/system alerts.
"""
from database import Database
from config import ALERT_TYPES


class AlertHandler:
    def __init__(self, db: Database):
        self._db = db
        self._latest_alert_id = None

    def process(self, data):
        """Process incoming alert from UART."""
        alert_type_code = data.get("alert_type", 0)
        alert_type = ALERT_TYPES.get(alert_type_code, f"UNKNOWN_{alert_type_code}")

        alert_data = {
            "type": alert_type,
            "lat": data.get("lat", 0),
            "lon": data.get("lon", 0),
            "image_b64": data.get("image_b64", "")
        }

        self._latest_alert_id = self._db.insert_alert(alert_data)
        return self._latest_alert_id

    def attach_image(self, image_b64):
        """Attach image to the latest alert (for chunked images)."""
        if self._latest_alert_id:
            conn = self._db._get_conn()
            conn.execute(
                "UPDATE alerts SET image_b64 = ? WHERE id = ?",
                (image_b64, self._latest_alert_id)
            )
            conn.commit()

    def get_alerts(self, alert_type=None, limit=100):
        """Get alerts with optional type filter."""
        return self._db.get_alerts(alert_type, limit)

    def acknowledge(self, alert_id, notes=""):
        """Acknowledge an alert."""
        self._db.acknowledge_alert(alert_id, notes)

    def get_today_count(self):
        """Get today's alert statistics."""
        return self._db.get_today_stats()

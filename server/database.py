"""
STASIS Server — Database Manager
SQLite database for telemetry, alerts, geofences, paths, and reports.
"""
import sqlite3
import json
import os
import threading
from datetime import datetime
from config import DB_PATH


class Database:
    _local = threading.local()

    def __init__(self):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        self._init_tables()

    def _get_conn(self):
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(DB_PATH)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
        return self._local.conn

    def _init_tables(self):
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT (datetime('now')),
                lat REAL,
                lon REAL,
                battery REAL,
                temperature REAL,
                accel_x INTEGER,
                accel_y INTEGER,
                accel_z INTEGER,
                rover_state INTEGER
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT (datetime('now')),
                type TEXT,
                lat REAL,
                lon REAL,
                image_b64 TEXT,
                acknowledged INTEGER DEFAULT 0,
                notes TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS geofences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                polygon_json TEXT,
                active INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS paths (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_hash TEXT,
                waypoints_json TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                times_used INTEGER DEFAULT 0,
                last_used TEXT
            );

            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                pdf_path TEXT,
                summary_json TEXT
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_telemetry_ts ON telemetry(timestamp);
            CREATE INDEX IF NOT EXISTS idx_alerts_ts ON alerts(timestamp);
            CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts(type);
        """)
        conn.commit()

    # ---- Telemetry ----
    def insert_telemetry(self, data):
        conn = self._get_conn()
        conn.execute(
            """INSERT INTO telemetry (lat, lon, battery, temperature,
               accel_x, accel_y, accel_z, rover_state)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (data.get("lat"), data.get("lon"), data.get("battery"),
             data.get("temp"), data.get("accel_x"), data.get("accel_y"),
             data.get("accel_z"), data.get("state"))
        )
        conn.commit()

    def get_telemetry(self, limit=100):
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM telemetry ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_telemetry_for_date(self, date_str):
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM telemetry WHERE date(timestamp) = ? ORDER BY id",
            (date_str,)
        ).fetchall()
        return [dict(r) for r in rows]

    # ---- Alerts ----
    def insert_alert(self, data):
        conn = self._get_conn()
        cursor = conn.execute(
            """INSERT INTO alerts (type, lat, lon, image_b64)
               VALUES (?, ?, ?, ?)""",
            (data.get("type"), data.get("lat"), data.get("lon"),
             data.get("image_b64", ""))
        )
        conn.commit()
        return cursor.lastrowid

    def get_alerts(self, alert_type=None, limit=100):
        conn = self._get_conn()
        if alert_type:
            rows = conn.execute(
                "SELECT * FROM alerts WHERE type = ? ORDER BY id DESC LIMIT ?",
                (alert_type, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def acknowledge_alert(self, alert_id, notes=""):
        conn = self._get_conn()
        conn.execute(
            "UPDATE alerts SET acknowledged = 1, notes = ? WHERE id = ?",
            (notes, alert_id)
        )
        conn.commit()

    def get_alerts_for_date(self, date_str):
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM alerts WHERE date(timestamp) = ? ORDER BY id",
            (date_str,)
        ).fetchall()
        return [dict(r) for r in rows]

    # ---- Geofences ----
    def get_geofences(self):
        conn = self._get_conn()
        rows = conn.execute("SELECT * FROM geofences ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]

    def create_geofence(self, name, polygon):
        conn = self._get_conn()
        cursor = conn.execute(
            "INSERT INTO geofences (name, polygon_json) VALUES (?, ?)",
            (name, json.dumps(polygon))
        )
        conn.commit()
        return cursor.lastrowid

    def update_geofence(self, gf_id, name=None, polygon=None, active=None):
        conn = self._get_conn()
        if name is not None:
            conn.execute("UPDATE geofences SET name = ? WHERE id = ?", (name, gf_id))
        if polygon is not None:
            conn.execute("UPDATE geofences SET polygon_json = ? WHERE id = ?",
                         (json.dumps(polygon), gf_id))
        if active is not None:
            conn.execute("UPDATE geofences SET active = ? WHERE id = ?", (active, gf_id))
        conn.commit()

    def delete_geofence(self, gf_id):
        conn = self._get_conn()
        conn.execute("DELETE FROM geofences WHERE id = ?", (gf_id,))
        conn.commit()

    def get_active_geofence(self):
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM geofences WHERE active = 1 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None

    # ---- Paths ----
    def save_path(self, location_hash, waypoints):
        conn = self._get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO paths (location_hash, waypoints_json, last_used)
               VALUES (?, ?, datetime('now'))""",
            (location_hash, json.dumps(waypoints))
        )
        conn.commit()

    def get_paths(self):
        conn = self._get_conn()
        rows = conn.execute("SELECT * FROM paths ORDER BY last_used DESC").fetchall()
        return [dict(r) for r in rows]

    # ---- Reports ----
    def save_report(self, date_str, pdf_path, summary):
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO reports (date, pdf_path, summary_json) VALUES (?, ?, ?)",
            (date_str, pdf_path, json.dumps(summary))
        )
        conn.commit()

    def get_reports(self):
        conn = self._get_conn()
        rows = conn.execute("SELECT * FROM reports ORDER BY date DESC").fetchall()
        return [dict(r) for r in rows]

    def get_report_by_date(self, date_str):
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM reports WHERE date = ?", (date_str,)
        ).fetchone()
        return dict(row) if row else None

    # ---- Settings ----
    def get_setting(self, key, default=None):
        conn = self._get_conn()
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key, value):
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, str(value))
        )
        conn.commit()

    def get_all_settings(self):
        conn = self._get_conn()
        rows = conn.execute("SELECT * FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}

    # ---- Stats ----
    def get_today_stats(self):
        conn = self._get_conn()
        today = datetime.now().strftime("%Y-%m-%d")

        tel_count = conn.execute(
            "SELECT COUNT(*) as c FROM telemetry WHERE date(timestamp) = ?", (today,)
        ).fetchone()["c"]

        alert_count = conn.execute(
            "SELECT COUNT(*) as c FROM alerts WHERE date(timestamp) = ?", (today,)
        ).fetchone()["c"]

        unack_count = conn.execute(
            "SELECT COUNT(*) as c FROM alerts WHERE acknowledged = 0"
        ).fetchone()["c"]

        return {
            "telemetry_count": tel_count,
            "alert_count": alert_count,
            "unacknowledged_alerts": unack_count
        }

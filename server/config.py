"""
STASIS Server — Configuration
All settings and constants for the backend server.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ---- Server ----
SERVER_HOST = os.getenv("STASIS_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("STASIS_PORT", "5000"))
SECRET_KEY = os.getenv("STASIS_SECRET", "stasis-secret-key-change-me")
DEBUG = os.getenv("STASIS_DEBUG", "false").lower() == "true"

# ---- Database ----
DB_PATH = os.getenv("STASIS_DB", "/var/stasis/stasis.db")

# ---- UART (to ESP32-C3) ----
UART_PORT = os.getenv("STASIS_UART", "/dev/ttyS0")
UART_BAUD = int(os.getenv("STASIS_UART_BAUD", "9600"))

# ---- Reports ----
REPORT_DIR = os.getenv("STASIS_REPORTS", "/var/stasis/reports")
REPORT_TIME = os.getenv("STASIS_REPORT_TIME", "23:55")
SNAPSHOTS_DIR = os.getenv("STASIS_SNAPSHOTS", "/var/stasis/snapshots")

# ---- Charging ----
BATTERY_LOW_VOLTAGE = float(os.getenv("STASIS_BAT_LOW", "3.6"))
BATTERY_FULL_VOLTAGE = float(os.getenv("STASIS_BAT_FULL", "4.2"))
CHARGING_SCHEDULE_START = os.getenv("STASIS_CHARGE_START", "02:00")
CHARGING_SCHEDULE_END = os.getenv("STASIS_CHARGE_END", "06:00")
AUTO_RETURN_ENABLED = os.getenv("STASIS_AUTO_RETURN", "true").lower() == "true"

# ---- Charging Station GPS ----
STATION_LAT = float(os.getenv("STASIS_STATION_LAT", "0.0"))
STATION_LON = float(os.getenv("STASIS_STATION_LON", "0.0"))

# ---- Camera ----
CAM_STREAM_URL = os.getenv("STASIS_CAM_URL", "http://192.168.4.2:81/stream")
CAM_CAPTURE_URL = os.getenv("STASIS_CAM_CAPTURE", "http://192.168.4.2:81/capture")

# ---- GPIO (RPi) ----
CHARGING_RELAY_GPIO = int(os.getenv("STASIS_RELAY_PIN", "18"))
EMERGENCY_STOP_GPIO = int(os.getenv("STASIS_ESTOP_PIN", "27"))
BATTERY_CRITICAL_VOLTAGE = float(os.getenv("STASIS_BAT_CRITICAL", "3.3"))

# ---- Rover State Names ----
ROVER_STATES = {
    0: "IDLE",
    1: "NAVIGATING",
    2: "PATROLLING",
    3: "RETURNING",
    4: "STUCK",
    5: "CHARGING",
    6: "EMERGENCY"
}

# ---- Alert Type Names ----
ALERT_TYPES = {
    1: "HUMAN",
    2: "STUCK",
    3: "LOW_BATTERY",
    4: "TILT"
}

# ---- Command Types ----
CMD_GOTO = 1
CMD_STOP = 2
CMD_RETURN = 3
CMD_RESUME = 4

# ---- Dashboard ----
STATIC_DIR = os.getenv("STASIS_STATIC", os.path.join(os.path.dirname(__file__), "static"))

# ---- Server Info ----
SERVER_VERSION = "1.0.0"

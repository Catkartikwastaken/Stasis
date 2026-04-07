"""
STASIS Server — Main Application
Flask + Flask-SocketIO entry point with REST API and real-time events.
"""
import os
import signal
import sys
import schedule
import time
import threading
from datetime import datetime

from flask import Flask, jsonify, request, send_from_directory, send_file
from flask_socketio import SocketIO
from flask_cors import CORS

from config import (SERVER_HOST, SERVER_PORT, SECRET_KEY, DEBUG,
                    STATIC_DIR, CMD_GOTO, CMD_STOP, CMD_RETURN, CMD_RESUME,
                    CAM_STREAM_URL, CAM_CAPTURE_URL, REPORT_DIR,
                    REPORT_TIME, SERVER_VERSION, STATION_LAT, STATION_LON,
                    DB_PATH, SNAPSHOTS_DIR)
from database import Database
from uart_handler import UARTHandler
from telemetry_handler import TelemetryHandler
from alert_handler import AlertHandler
from report_generator import ReportGenerator
from charging_controller import ChargingController
from geofence_manager import GeofenceManager
from path_manager import PathManager

# ---- Initialize Flask ----
app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")
app.config["SECRET_KEY"] = SECRET_KEY
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# ---- Initialize Services ----
db = Database()
telemetry_handler = TelemetryHandler(db)
alert_handler = AlertHandler(db)
geofence_manager = GeofenceManager(db)
path_manager = PathManager(db)
report_generator = ReportGenerator(db)

uart = UARTHandler(
    socketio=socketio,
    telemetry_handler=telemetry_handler,
    alert_handler=alert_handler
)
charging_controller = ChargingController(telemetry_handler, uart)

# ============================================================
# REST API — /api/v1
# ============================================================

@app.route("/api/v1/status")
def api_status():
    status = telemetry_handler.get_status()
    status["server_version"] = SERVER_VERSION
    status["uptime"] = int(time.time() - app_start_time)
    return jsonify(status)


@app.route("/api/v1/telemetry")
def api_telemetry():
    limit = request.args.get("limit", 100, type=int)
    data = telemetry_handler.get_history(limit)
    return jsonify(data)


@app.route("/api/v1/alerts")
def api_alerts():
    alert_type = request.args.get("type")
    limit = request.args.get("limit", 100, type=int)
    data = alert_handler.get_alerts(alert_type, limit)
    return jsonify(data)


@app.route("/api/v1/alerts/<int:alert_id>/ack", methods=["POST"])
def api_ack_alert(alert_id):
    notes = request.json.get("notes", "") if request.json else ""
    alert_handler.acknowledge(alert_id, notes)
    return jsonify({"status": "ok", "alert_id": alert_id})


@app.route("/api/v1/geofences")
def api_get_geofences():
    return jsonify(geofence_manager.get_all())


@app.route("/api/v1/geofences", methods=["POST"])
def api_create_geofence():
    data = request.json
    name = data.get("name", "Untitled")
    polygon = data.get("polygon", [])
    gf_id = geofence_manager.create(name, polygon)
    return jsonify({"status": "ok", "id": gf_id})


@app.route("/api/v1/geofences/<int:gf_id>", methods=["DELETE"])
def api_delete_geofence(gf_id):
    geofence_manager.delete(gf_id)
    return jsonify({"status": "ok"})


@app.route("/api/v1/geofences/<int:gf_id>/activate", methods=["POST"])
def api_activate_geofence(gf_id):
    geofence_manager.activate(gf_id)
    # Send updated geofence to rover
    gf_lats, gf_lons = geofence_manager.get_active_polygon_arrays()
    if gf_lats:
        uart.send_command(CMD_GOTO, 0, 0, gf_lats, gf_lons)
    return jsonify({"status": "ok", "id": gf_id})


@app.route("/api/v1/commands/goto", methods=["POST"])
def api_cmd_goto():
    data = request.json
    lat = data.get("lat", 0)
    lon = data.get("lon", 0)
    gf_lats, gf_lons = geofence_manager.get_active_polygon_arrays()
    uart.send_command(CMD_GOTO, lat, lon, gf_lats, gf_lons)
    return jsonify({"status": "ok", "command": "goto", "lat": lat, "lon": lon})


@app.route("/api/v1/commands/stop", methods=["POST"])
def api_cmd_stop():
    uart.send_command(CMD_STOP)
    return jsonify({"status": "ok", "command": "stop"})


@app.route("/api/v1/commands/return", methods=["POST"])
def api_cmd_return():
    uart.send_command(CMD_RETURN, STATION_LAT, STATION_LON)
    return jsonify({"status": "ok", "command": "return"})


@app.route("/api/v1/commands/resume", methods=["POST"])
def api_cmd_resume():
    uart.send_command(CMD_RESUME)
    return jsonify({"status": "ok", "command": "resume"})


@app.route("/api/v1/reports")
def api_reports():
    return jsonify(db.get_reports())


@app.route("/api/v1/reports/<date>/pdf")
def api_report_pdf(date):
    report = db.get_report_by_date(date)
    if report and os.path.exists(report["pdf_path"]):
        return send_file(report["pdf_path"], mimetype="application/pdf")
    return jsonify({"error": "Report not found"}), 404


@app.route("/api/v1/reports/generate", methods=["POST"])
def api_generate_report():
    data = request.json or {}
    date = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    try:
        report_generator.generate_daily_report(date)
        return jsonify({"status": "ok", "date": date})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/stream/url")
def api_stream_url():
    return jsonify({"url": CAM_STREAM_URL, "capture_url": CAM_CAPTURE_URL})


@app.route("/api/v1/settings", methods=["GET"])
def api_get_settings():
    return jsonify(db.get_all_settings())


@app.route("/api/v1/settings", methods=["POST"])
def api_save_settings():
    data = request.json
    for key, value in data.items():
        db.set_setting(key, value)
    return jsonify({"status": "ok"})


@app.route("/api/v1/health")
def api_health():
    return jsonify({
        "status": "ok",
        "uptime": int(time.time() - app_start_time),
        "uart_connected": uart.is_connected() if hasattr(uart, 'is_connected') else True,
        "db_path": db._get_conn() is not None,
        "server_version": SERVER_VERSION
    })


# ============================================================
# Socket.IO Events
# ============================================================

@socketio.on("connect")
def handle_connect():
    print("[WS] Client connected")
    socketio.emit("rover_state", telemetry_handler.get_status())


@socketio.on("disconnect")
def handle_disconnect():
    print("[WS] Client disconnected")


@socketio.on("command")
def handle_command(data):
    cmd = data.get("command", "")
    if cmd == "stop":
        uart.send_command(CMD_STOP)
    elif cmd == "return":
        uart.send_command(CMD_RETURN, STATION_LAT, STATION_LON)
    elif cmd == "resume":
        uart.send_command(CMD_RESUME)
    elif cmd == "goto":
        lat = data.get("lat", 0)
        lon = data.get("lon", 0)
        gf_lats, gf_lons = geofence_manager.get_active_polygon_arrays()
        uart.send_command(CMD_GOTO, lat, lon, gf_lats, gf_lons)
    socketio.emit("rover_state", telemetry_handler.get_status())


@socketio.on("ack_alert")
def handle_ack_alert(data):
    alert_id = data.get("id")
    notes = data.get("notes", "")
    if alert_id:
        alert_handler.acknowledge(alert_id, notes)


# ============================================================
# Static Files (React Dashboard)
# ============================================================

@app.route("/")
def serve_dashboard():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/<path:path>")
def serve_static(path):
    if os.path.exists(os.path.join(STATIC_DIR, path)):
        return send_from_directory(STATIC_DIR, path)
    return send_from_directory(STATIC_DIR, "index.html")


# ============================================================
# Scheduled Tasks
# ============================================================

def schedule_loop():
    while True:
        schedule.run_pending()
        time.sleep(30)


# ============================================================
# Main
# ============================================================

app_start_time = time.time()


def shutdown_handler(signum, frame):
    print("\n[SERVER] Shutting down...")
    uart.stop()
    charging_controller.stop()
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    print(f"\n{'='*50}")
    print(f"  STASIS Server v{SERVER_VERSION}")
    print(f"  http://{SERVER_HOST}:{SERVER_PORT}")
    print(f"{'='*50}\n")

    # Ensure required directories exist
    for d in [os.path.dirname(DB_PATH), REPORT_DIR, SNAPSHOTS_DIR, "/var/log/stasis"]:
        os.makedirs(d, exist_ok=True)

    # Start UART
    uart.start()

    # Start charging controller
    charging_controller.start()

    # Schedule daily report
    schedule.every().day.at(REPORT_TIME).do(report_generator.generate_daily_report)
    sched_thread = threading.Thread(target=schedule_loop, daemon=True)
    sched_thread.start()

    # Run server
    socketio.run(app, host=SERVER_HOST, port=SERVER_PORT, debug=DEBUG)

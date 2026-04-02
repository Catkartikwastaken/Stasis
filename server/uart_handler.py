"""
STASIS Server — UART Handler
Pyserial communication with ESP32-C3 Mini bridge.
"""
import json
import threading
import time
import serial
from config import UART_PORT, UART_BAUD


class UARTHandler:
    def __init__(self, socketio=None, telemetry_handler=None, alert_handler=None):
        self._serial = None
        self._running = False
        self._thread = None
        self._socketio = socketio
        self._telemetry_handler = telemetry_handler
        self._alert_handler = alert_handler
        self._image_buffer = ""
        self._lock = threading.Lock()

    def start(self):
        try:
            self._serial = serial.Serial(
                port=UART_PORT,
                baudrate=UART_BAUD,
                timeout=1,
                write_timeout=2
            )
            self._running = True
            self._thread = threading.Thread(target=self._read_loop, daemon=True)
            self._thread.start()
            print(f"[UART] Connected to {UART_PORT} @ {UART_BAUD}")
            return True
        except Exception as e:
            print(f"[UART] Connection failed: {e}")
            return False

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        if self._serial and self._serial.is_open:
            self._serial.close()
        print("[UART] Stopped")

    def send(self, data):
        """Send JSON data to ESP32-C3 via UART."""
        if not self._serial or not self._serial.is_open:
            print("[UART] Not connected")
            return False

        try:
            with self._lock:
                json_str = json.dumps(data) + "\n"
                self._serial.write(json_str.encode())
                self._serial.flush()
            return True
        except Exception as e:
            print(f"[UART] Send error: {e}")
            return False

    def send_command(self, command, target_lat=0, target_lon=0,
                     geofence_lats=None, geofence_lons=None):
        """Send a command to the rover via ESP32-C3 bridge."""
        data = {
            "type": "command",
            "command": command,
            "target_lat": target_lat,
            "target_lon": target_lon,
            "geofence_lats": geofence_lats or [],
            "geofence_lons": geofence_lons or []
        }
        return self.send(data)

    def send_charging_control(self, enable):
        """Control charging relay."""
        return self.send({"type": "charging", "enable": enable})

    def send_emergency_stop(self):
        """Trigger emergency stop."""
        return self.send({"type": "emergency"})

    def _read_loop(self):
        buffer = ""
        while self._running:
            try:
                if self._serial and self._serial.in_waiting:
                    data = self._serial.read(self._serial.in_waiting).decode("utf-8", errors="ignore")
                    buffer += data

                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if line and line.startswith("{"):
                            self._process_message(line)
                else:
                    time.sleep(0.01)
            except Exception as e:
                print(f"[UART] Read error: {e}")
                time.sleep(1)

    def _process_message(self, raw):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return

        msg_type = data.get("type", "")

        if msg_type == "telemetry":
            if self._telemetry_handler:
                self._telemetry_handler.process(data)
            if self._socketio:
                self._socketio.emit("telemetry", data)

        elif msg_type == "alert":
            if self._alert_handler:
                self._alert_handler.process(data)
            if self._socketio:
                self._socketio.emit("alert", data)

        elif msg_type == "image_chunk":
            self._handle_image_chunk(data)

        elif msg_type == "watchdog":
            print(f"[UART] Watchdog: {data.get('message')}")
            if self._socketio:
                self._socketio.emit("connection", {"status": "lost"})

    def _handle_image_chunk(self, data):
        if data.get("first"):
            self._image_buffer = ""
        self._image_buffer += data.get("data", "")
        if data.get("last"):
            # Complete image received — attach to latest alert
            if self._alert_handler:
                self._alert_handler.attach_image(self._image_buffer)
            self._image_buffer = ""

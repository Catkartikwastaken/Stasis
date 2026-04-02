"""
STASIS Server — Charging Controller
Monitor battery and manage charging schedule.
"""
import threading
import time
from datetime import datetime
from config import (BATTERY_LOW_VOLTAGE, CHARGING_SCHEDULE_START,
                    CHARGING_SCHEDULE_END, AUTO_RETURN_ENABLED,
                    STATION_LAT, STATION_LON, CMD_RETURN)


class ChargingController:
    def __init__(self, telemetry_handler, uart_handler):
        self._telemetry = telemetry_handler
        self._uart = uart_handler
        self._running = False
        self._thread = None
        self._return_sent = False
        self._charging_active = False

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        print("[CHARGING] Controller started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)

    def _monitor_loop(self):
        while self._running:
            try:
                self._check_battery()
                self._check_schedule()
                self._check_docking()
            except Exception as e:
                print(f"[CHARGING] Error: {e}")
            time.sleep(5)

    def _check_battery(self):
        """If battery is low, send RETURN command."""
        if not AUTO_RETURN_ENABLED:
            return

        status = self._telemetry.get_status()
        voltage = status.get("battery_voltage", 4.2)
        state = status.get("state_code", 0)

        # Don't send if already returning, charging, or idle
        if state in (3, 5, 0):  # RETURNING, CHARGING, IDLE
            self._return_sent = False
            return

        if voltage < BATTERY_LOW_VOLTAGE and voltage > 0 and not self._return_sent:
            print(f"[CHARGING] Low battery ({voltage:.2f}V), sending RETURN")
            self._uart.send_command(
                CMD_RETURN,
                target_lat=STATION_LAT,
                target_lon=STATION_LON
            )
            self._return_sent = True

    def _check_schedule(self):
        """Force return during scheduled charging window."""
        now = datetime.now()
        current_time = now.strftime("%H:%M")

        in_window = CHARGING_SCHEDULE_START <= current_time <= CHARGING_SCHEDULE_END

        if in_window:
            status = self._telemetry.get_status()
            state = status.get("state_code", 0)
            # If rover is not at station during charging window
            if state not in (0, 3, 5):  # Not IDLE, RETURNING, or CHARGING
                if not self._return_sent:
                    print("[CHARGING] Scheduled charging window, sending RETURN")
                    self._uart.send_command(
                        CMD_RETURN,
                        target_lat=STATION_LAT,
                        target_lon=STATION_LON
                    )
                    self._return_sent = True
        else:
            self._return_sent = False

    def _check_docking(self):
        """Activate charging relay when rover is docked."""
        status = self._telemetry.get_status()
        lat = status.get("lat", 0)
        lon = status.get("lon", 0)
        state = status.get("state_code", 0)

        if STATION_LAT == 0 and STATION_LON == 0:
            return

        # Check if rover is within 2m of station
        import math
        dist = self._haversine(lat, lon, STATION_LAT, STATION_LON)

        if dist < 2.0 and state in (3, 5, 0):  # RETURNING, CHARGING, IDLE
            if not self._charging_active:
                self._uart.send_charging_control(True)
                self._charging_active = True
                print("[CHARGING] Rover docked, charging enabled")
        else:
            if self._charging_active:
                self._uart.send_charging_control(False)
                self._charging_active = False

    @staticmethod
    def _haversine(lat1, lon1, lat2, lon2):
        import math
        R = 6371000
        dLat = math.radians(lat2 - lat1)
        dLon = math.radians(lon2 - lon1)
        a = (math.sin(dLat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dLon / 2) ** 2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

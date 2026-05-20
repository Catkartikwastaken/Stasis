from __future__ import annotations

import argparse
import json
import logging
import math
import os
import queue
import signal
import threading
import time
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

import websocket


ROVER_TYPE = "rover"


@dataclass
class PinConfig:
    # BCM numbering on the Raspberry Pi 2B 40-pin header.
    left_motor_forward: int = 5
    left_motor_reverse: int = 6
    right_motor_forward: int = 13
    right_motor_reverse: int = 19
    ultrasonic_trig: int = 23
    ultrasonic_echo: int = 24
    scanner_servo: int = 18


@dataclass
class MotionConfig:
    turn_kp: float = 0.8
    turn_tolerance_deg: float = 5.0
    turn_min_pwm: float = 35.0
    turn_max_pwm: float = 85.0
    drive_pwm: float = 70.0
    drive_ms_per_cm: float = 50.0
    turn_timeout_seconds: float = 12.0
    telemetry_interval_seconds: float = 0.5
    heartbeat_interval_seconds: float = 5.0
    scan_step_deg: int = 30
    scan_settle_seconds: float = 0.25


@dataclass
class SensorConfig:
    i2c_bus: int = 1
    mpu6050_address: int = 0x68
    hmc5883l_address: int = 0x1E
    compass_declination_deg: float = 0.0
    gyro_calibration_samples: int = 300
    gyro_deadband_deg_per_sec: float = 0.25


@dataclass
class HardwareConfig:
    direct_motor_control: bool = True
    i2c_enabled: bool = False
    mpu6050_enabled: bool = False
    compass_enabled: bool = False
    ultrasonic_enabled: bool = False
    scanner_servo_enabled: bool = False
    require_heading_for_goto: bool = False
    open_loop_turn_degrees_per_second: float = 90.0
    obstacle_stop_distance_cm: float = 25.0
    obstacle_check_interval_seconds: float = 0.1


@dataclass
class RoverConfig:
    server_host: str = ""
    server_port: int = 5000
    websocket_path: str = "/ws/rover"
    rover_id: str = "rpi2b_rover"
    simulate: bool = False
    pins: PinConfig = field(default_factory=PinConfig)
    motion: MotionConfig = field(default_factory=MotionConfig)
    sensors: SensorConfig = field(default_factory=SensorConfig)
    hardware: HardwareConfig = field(default_factory=HardwareConfig)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "RoverConfig":
        allowed = {field.name for field in fields(cls)}
        values = {key: value for key, value in data.items() if key in allowed}
        if "pins" in values:
            values["pins"] = _dataclass_from_mapping(PinConfig, values["pins"])
        if "motion" in values:
            values["motion"] = _dataclass_from_mapping(MotionConfig, values["motion"])
        if "sensors" in values:
            values["sensors"] = _dataclass_from_mapping(SensorConfig, values["sensors"])
        if "hardware" in values:
            values["hardware"] = _dataclass_from_mapping(HardwareConfig, values["hardware"])
        return cls(**values)


def _dataclass_from_mapping(dataclass_type: Any, data: dict[str, Any]) -> Any:
    allowed = {field.name for field in fields(dataclass_type)}
    return dataclass_type(**{key: value for key, value in data.items() if key in allowed})


def normalize_angle_degrees(angle: float) -> float:
    while angle > 180.0:
        angle -= 360.0
    while angle < -180.0:
        angle += 360.0
    return angle


def normalize_heading_degrees(angle: float) -> float:
    return angle % 360.0


def read_config(path: Path | None) -> RoverConfig:
    config = RoverConfig()
    if path is not None and path.exists():
        config = RoverConfig.from_mapping(json.loads(path.read_text(encoding="utf-8")))

    env_server = os.getenv("STASIS_SERVER_HOST")
    env_rover_id = os.getenv("STASIS_ROVER_ID")
    if env_server:
        config.server_host = env_server
    if env_rover_id:
        config.rover_id = env_rover_id
    return config


class HardwareBase:
    def setup(self) -> None:
        raise NotImplementedError

    def update(self) -> None:
        raise NotImplementedError

    def read_heading(self) -> float | None:
        raise NotImplementedError

    def set_motors(self, left_speed: float, right_speed: float) -> None:
        raise NotImplementedError

    def stop_motors(self) -> None:
        self.set_motors(0.0, 0.0)

    def scan(self) -> list[dict[str, float]]:
        raise NotImplementedError

    def front_distance_cm(self) -> float | None:
        raise NotImplementedError

    def cleanup(self) -> None:
        raise NotImplementedError


class SimulatedHardware(HardwareBase):
    def __init__(self, config: RoverConfig) -> None:
        self.config = config
        self.heading = 0.0
        self.last_update = time.monotonic()

    def setup(self) -> None:
        logging.info("Simulation mode enabled; no GPIO or I2C hardware will be used")

    def update(self) -> None:
        self.last_update = time.monotonic()

    def read_heading(self) -> float:
        return self.heading

    def set_motors(self, left_speed: float, right_speed: float) -> None:
        if left_speed == 0 and right_speed == 0:
            return
        turn_rate = (right_speed - left_speed) * 0.8
        self.heading = normalize_heading_degrees(self.heading + turn_rate * 0.02)

    def scan(self) -> list[dict[str, float]]:
        return [
            {"angle": float(angle), "distance": 120.0 + angle / 3.0}
            for angle in range(0, 181, self.config.motion.scan_step_deg)
        ]

    def front_distance_cm(self) -> float | None:
        return None

    def cleanup(self) -> None:
        self.stop_motors()


class MotorDriver:
    def __init__(self, gpio: Any, pins: PinConfig) -> None:
        self.gpio = gpio
        self.pins = pins
        self.pwm_by_pin: dict[int, Any] = {}

    def setup(self) -> None:
        for pin in (
            self.pins.left_motor_forward,
            self.pins.left_motor_reverse,
            self.pins.right_motor_forward,
            self.pins.right_motor_reverse,
        ):
            self.gpio.setup(pin, self.gpio.OUT)
            pwm = self.gpio.PWM(pin, 1000)
            pwm.start(0)
            self.pwm_by_pin[pin] = pwm
        self.stop()

    def _set_pair(self, forward_pin: int, reverse_pin: int, speed: float) -> None:
        speed = max(-100.0, min(100.0, speed))
        forward = self.pwm_by_pin[forward_pin]
        reverse = self.pwm_by_pin[reverse_pin]

        if speed > 0:
            forward.ChangeDutyCycle(speed)
            reverse.ChangeDutyCycle(0)
        elif speed < 0:
            forward.ChangeDutyCycle(0)
            reverse.ChangeDutyCycle(abs(speed))
        else:
            forward.ChangeDutyCycle(0)
            reverse.ChangeDutyCycle(0)

    def set_speeds(self, left_speed: float, right_speed: float) -> None:
        self._set_pair(self.pins.left_motor_forward, self.pins.left_motor_reverse, left_speed)
        self._set_pair(self.pins.right_motor_forward, self.pins.right_motor_reverse, right_speed)

    def stop(self) -> None:
        self.set_speeds(0.0, 0.0)

    def cleanup(self) -> None:
        self.stop()
        for pwm in self.pwm_by_pin.values():
            pwm.stop()


class MPU6050:
    GYRO_ZOUT_H = 0x47
    PWR_MGMT_1 = 0x6B
    GYRO_CONFIG = 0x1B
    CONFIG = 0x1A

    def __init__(self, bus: Any, address: int, sensor_config: SensorConfig) -> None:
        self.bus = bus
        self.address = address
        self.sensor_config = sensor_config
        self.gyro_z_bias = 0.0
        self.yaw_deg = 0.0
        self.last_update = time.monotonic()
        self.ready = False

    def setup(self) -> None:
        self.bus.write_byte_data(self.address, self.PWR_MGMT_1, 0x00)
        self.bus.write_byte_data(self.address, self.GYRO_CONFIG, 0x08)  # +/- 500 deg/s
        self.bus.write_byte_data(self.address, self.CONFIG, 0x04)  # roughly 21 Hz bandwidth
        time.sleep(0.1)
        self.calibrate()
        self.ready = True
        logging.info("MPU6050 ready")

    def read_s16(self, register: int) -> int:
        high = self.bus.read_byte_data(self.address, register)
        low = self.bus.read_byte_data(self.address, register + 1)
        value = (high << 8) | low
        return value - 65536 if value & 0x8000 else value

    def read_gyro_z_deg_per_sec(self) -> float:
        return self.read_s16(self.GYRO_ZOUT_H) / 65.5

    def calibrate(self) -> None:
        samples = max(1, self.sensor_config.gyro_calibration_samples)
        logging.info("Calibrating MPU6050 gyro; keep the rover still")
        total = 0.0
        for _ in range(samples):
            total += self.read_gyro_z_deg_per_sec()
            time.sleep(0.005)
        self.gyro_z_bias = total / samples
        self.yaw_deg = 0.0
        self.last_update = time.monotonic()
        logging.info("Gyro Z bias: %.3f deg/s", self.gyro_z_bias)

    def update(self) -> None:
        if not self.ready:
            return

        now = time.monotonic()
        dt = now - self.last_update
        self.last_update = now
        gyro_z = self.read_gyro_z_deg_per_sec() - self.gyro_z_bias
        if abs(gyro_z) < self.sensor_config.gyro_deadband_deg_per_sec:
            gyro_z = 0.0
        self.yaw_deg = normalize_angle_degrees(self.yaw_deg + gyro_z * dt)


class HMC5883L:
    def __init__(self, bus: Any, address: int, declination_deg: float) -> None:
        self.bus = bus
        self.address = address
        self.declination_deg = declination_deg
        self.ready = False

    def setup(self) -> None:
        self.bus.write_byte_data(self.address, 0x00, 0x70)
        self.bus.write_byte_data(self.address, 0x01, 0x20)
        self.bus.write_byte_data(self.address, 0x02, 0x00)
        self.ready = True
        logging.info("GY-271/HMC5883L compass ready")

    def read_s16_pair(self, high_register: int) -> int:
        high = self.bus.read_byte_data(self.address, high_register)
        low = self.bus.read_byte_data(self.address, high_register + 1)
        value = (high << 8) | low
        return value - 65536 if value & 0x8000 else value

    def heading(self) -> float | None:
        if not self.ready:
            return None

        x = self.read_s16_pair(0x03)
        y = self.read_s16_pair(0x07)
        heading = math.degrees(math.atan2(y, x)) + self.declination_deg
        return normalize_heading_degrees(heading)


class UltrasonicSensor:
    def __init__(self, gpio: Any, trig_pin: int, echo_pin: int) -> None:
        self.gpio = gpio
        self.trig_pin = trig_pin
        self.echo_pin = echo_pin

    def setup(self) -> None:
        self.gpio.setup(self.trig_pin, self.gpio.OUT)
        self.gpio.setup(self.echo_pin, self.gpio.IN)
        self.gpio.output(self.trig_pin, False)
        time.sleep(0.05)

    def distance_cm(self) -> float:
        self.gpio.output(self.trig_pin, False)
        time.sleep(0.000002)
        self.gpio.output(self.trig_pin, True)
        time.sleep(0.00001)
        self.gpio.output(self.trig_pin, False)

        deadline = time.monotonic() + 0.03
        while self.gpio.input(self.echo_pin) == 0:
            if time.monotonic() > deadline:
                return -1.0
        pulse_start = time.monotonic()

        deadline = time.monotonic() + 0.03
        while self.gpio.input(self.echo_pin) == 1:
            if time.monotonic() > deadline:
                return -1.0
        pulse_end = time.monotonic()

        return (pulse_end - pulse_start) * 34300.0 / 2.0


class ServoScanner:
    def __init__(self, gpio: Any, servo_pin: int, sensor: UltrasonicSensor, motion: MotionConfig) -> None:
        self.gpio = gpio
        self.servo_pin = servo_pin
        self.sensor = sensor
        self.motion = motion
        self.pwm: Any = None

    def setup(self) -> None:
        self.gpio.setup(self.servo_pin, self.gpio.OUT)
        self.pwm = self.gpio.PWM(self.servo_pin, 50)
        self.pwm.start(0)
        self.write_angle(90)

    def write_angle(self, angle: int) -> None:
        angle = max(0, min(180, angle))
        duty_cycle = 2.5 + angle / 18.0
        self.pwm.ChangeDutyCycle(duty_cycle)
        time.sleep(0.05)
        self.pwm.ChangeDutyCycle(0)

    def scan(self) -> list[dict[str, float]]:
        readings = []
        for angle in range(0, 181, self.motion.scan_step_deg):
            self.write_angle(angle)
            time.sleep(self.motion.scan_settle_seconds)
            readings.append({"angle": float(angle), "distance": self.sensor.distance_cm()})
        self.write_angle(90)
        return readings

    def cleanup(self) -> None:
        if self.pwm is not None:
            self.pwm.stop()


class RealRoverHardware(HardwareBase):
    def __init__(self, config: RoverConfig) -> None:
        self.config = config
        self.gpio: Any = None
        self.bus: Any = None
        self.motors: MotorDriver | None = None
        self.imu: MPU6050 | None = None
        self.compass: HMC5883L | None = None
        self.ultrasonic: UltrasonicSensor | None = None
        self.scanner: ServoScanner | None = None

    def setup(self) -> None:
        try:
            import RPi.GPIO as GPIO
        except ImportError as exc:
            raise RuntimeError("RPi.GPIO is required on the Raspberry Pi. Use --simulate on a laptop.") from exc

        self.gpio = GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        if self.config.hardware.direct_motor_control:
            self.motors = MotorDriver(GPIO, self.config.pins)
            self.motors.setup()
        else:
            logging.warning("Direct Pi motor control is disabled; motor commands will be no-ops")

        self._setup_i2c()
        self._setup_scanner()

    def _setup_i2c(self) -> None:
        if not self.config.hardware.i2c_enabled:
            logging.info("I2C sensors disabled by config; using minimal-wire rover mode")
            return

        try:
            from smbus2 import SMBus
        except ImportError:
            logging.warning("smbus2 is not installed; MPU6050 and compass are disabled")
            return

        try:
            self.bus = SMBus(self.config.sensors.i2c_bus)
        except OSError:
            logging.exception("Could not open I2C bus %s", self.config.sensors.i2c_bus)
            return

        if self.config.hardware.mpu6050_enabled:
            self.imu = MPU6050(self.bus, self.config.sensors.mpu6050_address, self.config.sensors)
            try:
                self.imu.setup()
            except OSError:
                logging.exception("MPU6050 not found; gyro yaw is disabled")
                self.imu = None

        if self.config.hardware.compass_enabled:
            self.compass = HMC5883L(
                self.bus,
                self.config.sensors.hmc5883l_address,
                self.config.sensors.compass_declination_deg,
            )
            try:
                self.compass.setup()
            except OSError:
                logging.exception("GY-271/HMC5883L compass not found; compass heading is disabled")
                self.compass = None

    def _setup_scanner(self) -> None:
        if not self.config.hardware.ultrasonic_enabled:
            logging.info("Ultrasonic obstacle sensor disabled by config")
            return

        self.ultrasonic = UltrasonicSensor(
            self.gpio,
            self.config.pins.ultrasonic_trig,
            self.config.pins.ultrasonic_echo,
        )
        self.ultrasonic.setup()

        if not self.config.hardware.scanner_servo_enabled:
            logging.info("Scanner servo disabled by config; using fixed forward ultrasonic only")
            return

        self.scanner = ServoScanner(
            self.gpio,
            self.config.pins.scanner_servo,
            self.ultrasonic,
            self.config.motion,
        )
        self.scanner.setup()

    def update(self) -> None:
        if self.imu is not None:
            try:
                self.imu.update()
            except OSError:
                logging.exception("MPU6050 read failed; disabling gyro yaw")
                self.imu = None

    def read_heading(self) -> float | None:
        if self.compass is not None:
            try:
                heading = self.compass.heading()
            except OSError:
                logging.exception("Compass read failed; disabling compass heading")
                self.compass = None
                heading = None
            if heading is not None:
                return heading
        if self.imu is not None:
            return normalize_heading_degrees(self.imu.yaw_deg)
        return None

    def set_motors(self, left_speed: float, right_speed: float) -> None:
        if self.motors is not None:
            self.motors.set_speeds(left_speed, right_speed)

    def scan(self) -> list[dict[str, float]]:
        if self.scanner is None:
            distance = self.front_distance_cm()
            if distance is None:
                return []
            return [{"angle": 90.0, "distance": distance}]
        return self.scanner.scan()

    def front_distance_cm(self) -> float | None:
        if self.ultrasonic is None:
            return None
        distance = self.ultrasonic.distance_cm()
        if distance < 0:
            return None
        return distance

    def cleanup(self) -> None:
        if self.motors is not None:
            self.motors.cleanup()
        if self.scanner is not None:
            self.scanner.cleanup()
        if self.bus is not None:
            self.bus.close()
        if self.gpio is not None:
            self.gpio.cleanup()


class RoverClient:
    def __init__(self, config: RoverConfig, hardware: HardwareBase) -> None:
        self.config = config
        self.hardware = hardware
        self.ws: websocket.WebSocketApp | None = None
        self.connected = threading.Event()
        self.stop_requested = threading.Event()
        self.movement_cancel = threading.Event()
        self.command_queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self.send_lock = threading.Lock()
        self.distance_traveled_cm = 0.0
        self.last_heading = 0.0

    @property
    def websocket_url(self) -> str:
        return f"ws://{self.config.server_host}:{self.config.server_port}{self.config.websocket_path}"

    def send_json(self, payload: dict[str, Any]) -> None:
        if not self.connected.is_set() or self.ws is None:
            return
        message = json.dumps(payload, separators=(",", ":"))
        with self.send_lock:
            try:
                self.ws.send(message)
            except Exception:
                logging.exception("Could not send rover message")
                self.connected.clear()

    def on_open(self, ws: websocket.WebSocketApp) -> None:
        logging.info("Connected to %s", self.websocket_url)
        self.connected.set()
        self.send_json({"id": self.config.rover_id, "type": ROVER_TYPE})
        self.send_json({"status": "ready"})

    def on_close(self, ws: websocket.WebSocketApp, status_code: int, message: str) -> None:
        logging.warning("WebSocket closed: %s %s", status_code, message)
        self.connected.clear()
        self.hardware.stop_motors()

    def on_error(self, ws: websocket.WebSocketApp, error: Exception) -> None:
        logging.warning("WebSocket error: %s", error)

    def on_message(self, ws: websocket.WebSocketApp, message: str) -> None:
        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            logging.warning("Ignoring non-JSON message: %s", message)
            return

        if isinstance(payload, dict) and payload.get("cmd") == "stop":
            self.movement_cancel.set()
            self.hardware.stop_motors()
            self.send_json({"status": "stopped"})
        elif isinstance(payload, dict) and "cmd" in payload:
            self.command_queue.put(payload)
        else:
            logging.debug("Server message: %s", payload)

    def telemetry_loop(self) -> None:
        last_heartbeat = 0.0
        last_telemetry = 0.0
        while not self.stop_requested.is_set():
            now = time.monotonic()
            self.hardware.update()

            heading = self.hardware.read_heading()
            if heading is not None:
                self.last_heading = heading

            if now - last_telemetry >= self.config.motion.telemetry_interval_seconds:
                last_telemetry = now
                self.send_json(
                    {
                        "heading": self.last_heading,
                        "distance_traveled": self.distance_traveled_cm,
                    }
                )

            if now - last_heartbeat >= self.config.motion.heartbeat_interval_seconds:
                last_heartbeat = now
                self.send_json({"status": "ready"})

            time.sleep(0.02)

    def command_loop(self) -> None:
        while not self.stop_requested.is_set():
            try:
                command = self.command_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                self.handle_command(command)
            except Exception:
                logging.exception("Command failed: %s", command)
                self.hardware.stop_motors()
                self.send_json({"status": "command_error"})

    def handle_command(self, command: dict[str, Any]) -> None:
        cmd = command.get("cmd")
        if cmd == "goto":
            self.handle_goto(float(command.get("angle", 0.0)), float(command.get("distance", 0.0)))
        elif cmd == "scan":
            report: dict[str, Any] = {"type": "scan", "data": self.hardware.scan()}
            if command.get("target"):
                report["target"] = str(command["target"])
            self.send_json(report)
        elif cmd == "stop":
            self.hardware.stop_motors()
            self.send_json({"status": "stopped"})
        else:
            logging.warning("Unknown command: %s", command)

    def handle_goto(self, angle: float, distance_cm: float) -> None:
        self.movement_cancel.clear()
        heading = self.hardware.read_heading()
        if heading is None and self.config.hardware.require_heading_for_goto:
            self.hardware.stop_motors()
            self.send_json(
                {
                    "status": "imu_error",
                    "message": "No heading source available and require_heading_for_goto is enabled",
                }
            )
            return

        if heading is None:
            self.open_loop_turn_to_angle(angle)
        else:
            self.last_heading = heading
            self.turn_to_angle(angle)

        time.sleep(0.1)
        drive_status = "goal_reached"
        if not self.movement_cancel.is_set():
            drive_status = self.drive_forward(distance_cm)
        if self.movement_cancel.is_set():
            drive_status = "stopped"
        self.send_json({"status": drive_status})

    def turn_to_angle(self, target_angle: float) -> None:
        motion = self.config.motion
        target_angle = normalize_heading_degrees(target_angle)
        deadline = time.monotonic() + motion.turn_timeout_seconds

        while (
            time.monotonic() < deadline
            and not self.stop_requested.is_set()
            and not self.movement_cancel.is_set()
        ):
            self.hardware.update()
            heading = self.hardware.read_heading()
            if heading is None:
                break
            self.last_heading = heading
            error = normalize_angle_degrees(target_angle - heading)
            if abs(error) <= motion.turn_tolerance_deg:
                break

            speed = max(motion.turn_min_pwm, min(motion.turn_max_pwm, abs(error) * motion.turn_kp))
            if error > 0:
                self.hardware.set_motors(speed, -speed)
            else:
                self.hardware.set_motors(-speed, speed)
            time.sleep(0.01)

        self.hardware.stop_motors()

    def open_loop_turn_to_angle(self, target_angle: float) -> None:
        motion = self.config.motion
        target_angle = normalize_heading_degrees(target_angle)
        error = normalize_angle_degrees(target_angle - self.last_heading)
        turn_rate = max(1.0, self.config.hardware.open_loop_turn_degrees_per_second)
        duration = abs(error) / turn_rate
        if duration <= 0:
            return

        speed = max(motion.turn_min_pwm, min(motion.turn_max_pwm, abs(error) * motion.turn_kp))
        if error > 0:
            left_speed, right_speed = speed, -speed
        else:
            left_speed, right_speed = -speed, speed

        start = time.monotonic()
        while (
            time.monotonic() - start < duration
            and not self.stop_requested.is_set()
            and not self.movement_cancel.is_set()
        ):
            self.hardware.set_motors(left_speed, right_speed)
            time.sleep(0.01)

        self.hardware.stop_motors()
        if not self.movement_cancel.is_set():
            self.last_heading = target_angle

    def drive_forward(self, distance_cm: float) -> str:
        distance_cm = max(0.0, distance_cm)
        duration = distance_cm * self.config.motion.drive_ms_per_cm / 1000.0
        start = time.monotonic()
        start_distance = self.distance_traveled_cm
        last_obstacle_check = 0.0

        while (
            time.monotonic() - start < duration
            and not self.stop_requested.is_set()
            and not self.movement_cancel.is_set()
        ):
            self.hardware.update()
            now = time.monotonic()
            if now - last_obstacle_check >= self.config.hardware.obstacle_check_interval_seconds:
                last_obstacle_check = now
                front_distance = self.hardware.front_distance_cm()
                if (
                    front_distance is not None
                    and front_distance <= self.config.hardware.obstacle_stop_distance_cm
                ):
                    self.hardware.stop_motors()
                    return "obstacle_detected"

            progress = min(1.0, (time.monotonic() - start) / duration) if duration > 0 else 1.0
            self.distance_traveled_cm = start_distance + distance_cm * progress
            self.hardware.set_motors(self.config.motion.drive_pwm, self.config.motion.drive_pwm)
            time.sleep(0.01)

        self.distance_traveled_cm = start_distance + distance_cm
        self.hardware.stop_motors()
        return "goal_reached"

    def request_stop(self, *_args: Any) -> None:
        self.stop_requested.set()
        self.movement_cancel.set()
        self.connected.clear()
        self.hardware.stop_motors()
        if self.ws is not None:
            self.ws.close()

    def run(self) -> None:
        self.hardware.setup()
        threading.Thread(target=self.command_loop, name="command-loop", daemon=True).start()
        threading.Thread(target=self.telemetry_loop, name="telemetry-loop", daemon=True).start()

        while not self.stop_requested.is_set():
            logging.info("Connecting to %s as %s", self.websocket_url, self.config.rover_id)
            self.ws = websocket.WebSocketApp(
                self.websocket_url,
                on_open=self.on_open,
                on_close=self.on_close,
                on_error=self.on_error,
                on_message=self.on_message,
            )
            self.ws.run_forever(ping_interval=15, ping_timeout=3)
            self.connected.clear()
            self.hardware.stop_motors()
            if not self.stop_requested.is_set():
                time.sleep(3)

        self.hardware.cleanup()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="STASIS Raspberry Pi 2B rover client")
    parser.add_argument("--config", type=Path, default=Path("config.json"))
    parser.add_argument("--server", help="Laptop/server IP or hostname running Flask on port 5000")
    parser.add_argument("--port", type=int, help="Server WebSocket port")
    parser.add_argument("--rover-id", help="Rover client id expected by the server")
    parser.add_argument("--simulate", action="store_true", help="Run without GPIO/I2C hardware")
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=args.log_level.upper(), format="%(asctime)s %(levelname)s %(message)s")
    config = read_config(args.config)

    if args.server:
        config.server_host = args.server
    if args.port:
        config.server_port = args.port
    if args.rover_id:
        config.rover_id = args.rover_id
    if args.simulate:
        config.simulate = True

    if not config.server_host:
        raise SystemExit("Set server_host in config.json or pass --server <SERVER_IP>.")

    hardware: HardwareBase = SimulatedHardware(config) if config.simulate else RealRoverHardware(config)
    client = RoverClient(config, hardware)
    signal.signal(signal.SIGINT, client.request_stop)
    signal.signal(signal.SIGTERM, client.request_stop)
    client.run()


if __name__ == "__main__":
    main()

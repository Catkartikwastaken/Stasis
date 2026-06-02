"""
Stasis Forest Monitoring Rover - Raspberry Pi Client

This module runs on the Raspberry Pi (Rover Client) and establishes a WebSocket
connection with the host monitoring server. It receives navigation targets
and scanning requests, executing closed-loop PID turning, open-loop driving,
ultrasonic scanning, and sensor telemetry gathering.

Hardware Support:
- Direct DC Motor control via L911S H-Bridge connected directly to Pi GPIOs.
- ESP32-S3-delegated DC Motor control via UART/Serial interface (using SerialMotorDriver).
- Gyroscope yaw/imu sensing using MPU6050 over I2C.
- Compass heading sensing using HMC5883L/GY-271 over I2C.
- HC-SR04 Ultrasonic Distance Sensor for obstacle detection and scanning.
- SG90 servo motor for sweeping the ultrasonic sensor.
"""

from __future__ import annotations

import argparse
import base64
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

# Identifies the client device type to the server during WebSocket registration
ROVER_TYPE = "rover"

MODE_IDLE = "IDLE"
MODE_MANUAL = "MANUAL"
MODE_PATROL = "PATROL"
MODE_FOLLOW = "FOLLOW"
MODE_EMERGENCY_STOP = "EMERGENCY_STOP"
MODE_WAITING_DECISION = "IDLE_WAITING_DECISION"


@dataclass
class PinConfig:
    """
    GPIO Pin Allocations based on Broadcom (BCM) numbering on the 40-pin header.
    These are only used if direct Raspberry Pi GPIO hardware interfaces are enabled.
    """
    left_motor_forward: int = 5
    left_motor_reverse: int = 6
    right_motor_forward: int = 13
    right_motor_reverse: int = 19
    left_motor_enable: int | None = None
    right_motor_enable: int | None = None
    ultrasonic_trig: int = 23
    ultrasonic_echo: int = 24
    scanner_servo: int = 18


@dataclass
class MotionConfig:
    """
    Configuration parameters for movement calibration, PID constants, and timing timeouts.
    """
    turn_kp: float = 0.8                      # Proportional gain for closed-loop PID turning
    turn_tolerance_deg: float = 5.0           # Acceptable angular error margin to declare a turn complete
    turn_min_pwm: float = 35.0                # Minimum duty cycle to overcome static friction during turning
    turn_max_pwm: float = 85.0                # Cap on motor speed duty cycle during high-error PID turns
    drive_pwm: float = 70.0                   # Default forward driving speed duty cycle
    drive_ms_per_cm: float = 50.0             # Open-loop calibration constant mapping drive duration to distance
    turn_timeout_seconds: float = 12.0        # Timeout limit before aborting a closed-loop turn operation
    telemetry_interval_seconds: float = 0.5   # Periodicity of sending status packets back to the dashboard
    heartbeat_interval_seconds: float = 5.0   # Periodicity of keep-alive signals
    scan_step_deg: int = 30                   # Angle step increment during ultrasonic sonar sweep
    scan_settle_seconds: float = 0.25         # Delay to let servo stabilize before firing ultrasound trigger
    follow_base_pwm: float = 42.0
    follow_turn_pwm: float = 28.0
    follow_target_area_ratio: float = 0.16
    follow_deadband_ratio: float = 0.12
    follow_lost_timeout_seconds: float = 2.5
    follow_update_interval_seconds: float = 0.2


@dataclass
class SensorConfig:
    """
    Configuration for onboard I2C sensors (MPU6050 Gyro, HMC5883L Compass).
    """
    i2c_bus: int = 1
    mpu6050_address: int = 0x68
    hmc5883l_address: int = 0x1E
    compass_declination_deg: float = 0.0
    gyro_calibration_samples: int = 300
    gyro_deadband_deg_per_sec: float = 0.25


@dataclass
class HardwareConfig:
    """
    Switches to toggle physical hardware subsystems on/off, or enable serial communication delegation.
    """
    direct_motor_control: bool = True                     # Directly drive motor controller from Raspberry Pi GPIO pins
    motor_driver: str = "l911s"                           # Direct GPIO driver type: l911s or l298n
    esp32_serial_control: bool = False                    # Delegate L911S motor driving to ESP32-S3 over Serial
    esp32_serial_port: str = "/dev/ttyUSB0"               # Serial port device node (e.g. COM3 on Win, /dev/ttyUSB0 on Linux)
    esp32_baudrate: int = 115200                          # Baud rate matching ESP32 controller firmware
    i2c_enabled: bool = False                             # Master toggle for I2C communication
    mpu6050_enabled: bool = False                         # MPU6050 Inertial Measurement Unit toggle
    compass_enabled: bool = False                         # GY-271 / HMC5883L Magnetometer toggle
    ultrasonic_enabled: bool = False                      # HC-SR04 ultrasonic rangefinder toggle
    scanner_servo_enabled: bool = False                   # SG90 sweep servo toggle
    require_heading_for_goto: bool = False                # Reject navigation goals if no active IMU/Compass exists
    open_loop_turn_degrees_per_second: float = 90.0       # Fallback calibration constant for non-IMU turns
    obstacle_stop_distance_cm: float = 25.0               # Minimum distance threshold before emergency stopping
    obstacle_check_interval_seconds: float = 0.1          # Polling rate of ultrasonic sensor during drive forward


@dataclass
class CameraConfig:
    """
    USB webcam capture settings for frames sent from Raspberry Pi to the Windows server.
    """
    enabled: bool = True
    index: int = 0
    width: int = 640
    height: int = 480
    fps: int = 10
    jpeg_quality: int = 70
    upload_interval_seconds: float = 2.0


@dataclass
class RoverConfig:
    """
    Aggregated configuration structure containing system settings and sub-component configs.
    """
    server_host: str = ""
    server_port: int = 5000
    websocket_path: str = "/ws/rover"
    rover_id: str = "rpi2b_rover"
    simulate: bool = False
    pins: PinConfig = field(default_factory=PinConfig)
    motion: MotionConfig = field(default_factory=MotionConfig)
    sensors: SensorConfig = field(default_factory=SensorConfig)
    hardware: HardwareConfig = field(default_factory=HardwareConfig)
    camera: CameraConfig = field(default_factory=CameraConfig)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> RoverConfig:
        """
        Dynamically instantiates configurations from a nested dictionary structure.
        """
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
        if "camera" in values:
            values["camera"] = _dataclass_from_mapping(CameraConfig, values["camera"])
        return cls(**values)


def _dataclass_from_mapping(dataclass_type: Any, data: dict[str, Any]) -> Any:
    """
    Helper function to safely construct dataclasses from dynamic dictionaries.
    """
    allowed = {field.name for field in fields(dataclass_type)}
    return dataclass_type(**{key: value for key, value in data.items() if key in allowed})


def normalize_angle_degrees(angle: float) -> float:
    """
    Normalizes an angle to the [-180.0, 180.0] range.
    """
    while angle > 180.0:
        angle -= 360.0
    while angle < -180.0:
        angle += 360.0
    return angle


def normalize_heading_degrees(angle: float) -> float:
    """
    Normalizes an angle to the [0.0, 360.0) range for compass headings.
    """
    return angle % 360.0


def read_config(path: Path | None) -> RoverConfig:
    """
    Loads JSON configuration files and overlays environment variable settings.
    
    @param path The filepath to read config from.
    @return Fully initialized RoverConfig object.
    """
    config = RoverConfig()
    try:
        if path is not None and path.exists():
            config = RoverConfig.from_mapping(json.loads(path.read_text(encoding="utf-8")))
            logging.info("Configuration successfully loaded from %s", path)
    except Exception as exc:
        logging.error("Failed to parse config file: %s. Using safe defaults.", exc)

    env_server = os.getenv("STASIS_SERVER_HOST")
    env_rover_id = os.getenv("STASIS_ROVER_ID")
    if env_server:
        config.server_host = env_server
        logging.info("Overlayed server_host from environment: %s", env_server)
    if env_rover_id:
        config.rover_id = env_rover_id
        logging.info("Overlayed rover_id from environment: %s", env_rover_id)
    return config


class HardwareBase:
    """
    Abstract Hardware Base Class defining the mandatory interface for all
    physical and simulated rover platforms.
    """
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
    """
    Provides mock telemetry, simulated motor movement kinematics, and synthetic
    sensor output to support development and testing on personal computers without
    physical hardware dependencies.
    """
    def __init__(self, config: RoverConfig) -> None:
        self.config = config
        self.heading = 0.0
        self.last_update = time.monotonic()

    def setup(self) -> None:
        logging.info("Simulation mode enabled; no GPIO, I2C, or Serial hardware will be used")

    def update(self) -> None:
        self.last_update = time.monotonic()

    def read_heading(self) -> float:
        return self.heading

    def set_motors(self, left_speed: float, right_speed: float) -> None:
        if left_speed == 0.0 and right_speed == 0.0:
            return
        # Basic differential drive simulation mapping motor power mismatch to turn rate
        turn_rate = (right_speed - left_speed) * 0.8
        self.heading = normalize_heading_degrees(self.heading + turn_rate * 0.02)

    def scan(self) -> list[dict[str, float]]:
        # Returns a nice synthetic dome pattern of distance readings
        return [
            {"angle": float(angle), "distance": 120.0 + angle / 3.0}
            for angle in range(0, 181, self.config.motion.scan_step_deg)
        ]

    def front_distance_cm(self) -> float | None:
        return None

    def cleanup(self) -> None:
        self.stop_motors()
        logging.info("Simulated hardware cleaned up.")


class MotorDriver:
    """
    Drives two differential motor channels from Raspberry Pi BCM GPIO pins.

    L911S mode PWM-drives the two direction inputs per side.
    L298N mode drives IN1/IN2/IN3/IN4 digitally and PWM-drives ENA/ENB when
    enable pins are configured. If ENA/ENB are left jumpered high, L298N falls
    back to direction-pin PWM for compatibility.
    """
    def __init__(self, gpio: Any, pins: PinConfig, driver_type: str = "l911s") -> None:
        self.gpio = gpio
        self.pins = pins
        self.driver_type = driver_type.lower().strip()
        self.pwm_by_pin: dict[int, Any] = {}

    def setup(self) -> None:
        """
        Configures specified GPIO pins to output and starts PWM.
        """
        if self.driver_type not in {"l911s", "l298n"}:
            raise RuntimeError(f"Unsupported direct motor driver type: {self.driver_type}")

        logging.info("Configuring direct Raspberry Pi GPIO motor pins for %s...", self.driver_type.upper())
        try:
            direction_pins = (
                self.pins.left_motor_forward,
                self.pins.left_motor_reverse,
                self.pins.right_motor_forward,
                self.pins.right_motor_reverse,
            )
            enable_pins = tuple(
                pin for pin in (self.pins.left_motor_enable, self.pins.right_motor_enable)
                if pin is not None
            )

            for pin in direction_pins:
                self.gpio.setup(pin, self.gpio.OUT)
                self.gpio.output(pin, self.gpio.LOW)

            if self.driver_type == "l911s" or not enable_pins:
                for pin in direction_pins:
                    pwm = self.gpio.PWM(pin, 1000)
                    pwm.start(0)
                    self.pwm_by_pin[pin] = pwm
            else:
                for pin in enable_pins:
                    self.gpio.setup(pin, self.gpio.OUT)
                    pwm = self.gpio.PWM(pin, 1000)
                    pwm.start(0)
                    self.pwm_by_pin[pin] = pwm
            self.stop()
            logging.info("Direct GPIO motor driver setup complete.")
        except Exception as exc:
            logging.exception("Failed to configure RPi.GPIO pins for direct motor control")
            raise RuntimeError("Direct GPIO motor setup failed.") from exc

    def _set_pair(self, forward_pin: int, reverse_pin: int, speed: float) -> None:
        """
        Applies PWM signal based on motor direction.
        """
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

    def _set_l298n_pair(
        self,
        forward_pin: int,
        reverse_pin: int,
        enable_pin: int | None,
        speed: float,
    ) -> None:
        speed = max(-100.0, min(100.0, speed))

        if enable_pin is None:
            self._set_pair(forward_pin, reverse_pin, speed)
            return

        enable = self.pwm_by_pin[enable_pin]
        if speed > 0:
            self.gpio.output(forward_pin, self.gpio.HIGH)
            self.gpio.output(reverse_pin, self.gpio.LOW)
            enable.ChangeDutyCycle(speed)
        elif speed < 0:
            self.gpio.output(forward_pin, self.gpio.LOW)
            self.gpio.output(reverse_pin, self.gpio.HIGH)
            enable.ChangeDutyCycle(abs(speed))
        else:
            enable.ChangeDutyCycle(0)
            self.gpio.output(forward_pin, self.gpio.LOW)
            self.gpio.output(reverse_pin, self.gpio.LOW)

    def set_speeds(self, left_speed: float, right_speed: float) -> None:
        """
        Updates PWM duty cycles on both channels.
        """
        if self.driver_type == "l298n":
            self._set_l298n_pair(
                self.pins.left_motor_forward,
                self.pins.left_motor_reverse,
                self.pins.left_motor_enable,
                left_speed,
            )
            self._set_l298n_pair(
                self.pins.right_motor_forward,
                self.pins.right_motor_reverse,
                self.pins.right_motor_enable,
                right_speed,
            )
        else:
            self._set_pair(self.pins.left_motor_forward, self.pins.left_motor_reverse, left_speed)
            self._set_pair(self.pins.right_motor_forward, self.pins.right_motor_reverse, right_speed)

    def stop(self) -> None:
        self.set_speeds(0.0, 0.0)

    def cleanup(self) -> None:
        logging.info("Cleaning up MotorDriver...")
        self.stop()
        for pin in (
            self.pins.left_motor_forward,
            self.pins.left_motor_reverse,
            self.pins.right_motor_forward,
            self.pins.right_motor_reverse,
        ):
            try:
                self.gpio.output(pin, self.gpio.LOW)
            except Exception:
                pass
        for pwm in self.pwm_by_pin.values():
            try:
                pwm.stop()
            except Exception:
                pass
        self.pwm_by_pin.clear()


class SerialMotorDriver:
    """
    Drives motors by delegating commands to an ESP32-S3 over a Serial connection.
    
    This implements serial motor control protocol which offloads PWM generation
    and low-level driver switching from the Pi CPU.
    """
    def __init__(self, port: str, baudrate: int) -> None:
        self.port = port
        self.baudrate = baudrate
        self.serial: Any = None
        self.lock = threading.Lock()

    def setup(self) -> None:
        """
        Initializes connection over UART/Serial port.
        """
        try:
            import serial
        except ImportError as exc:
            raise RuntimeError(
                "pyserial is required to use ESP32 Serial Motor Control. "
                "Please run 'pip install pyserial' or verify your requirements installation."
            ) from exc

        logging.info("Connecting to ESP32 motor controller at %s (%d baud)...", self.port, self.baudrate)
        try:
            # We open with a timeout so read operations don't block indefinitely
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=0.1,
                write_timeout=0.5
            )
            # Allow the ESP32-S3 USB stack or UART driver to stabilize after DTR toggles
            time.sleep(1.0)
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            logging.info("Successfully connected to ESP32 motor controller.")
        except Exception as e:
            logging.exception("Failed to open serial port %s", self.port)
            raise RuntimeError(f"Could not connect to ESP32 motor controller on {self.port}. Verify port and permissions.") from e

    def set_speeds(self, left_speed: float, right_speed: float) -> None:
        """
        Constructs and transmits the motor speed command packet over Serial.
        Format: "M:left_speed,right_speed\n"
        """
        if self.serial is None or not self.serial.is_open:
            logging.error("Serial port is disconnected. Cannot set motor speeds.")
            return

        # Clamp and cast to integer speed percentages
        left_int = int(max(-100.0, min(100.0, left_speed)))
        right_int = int(max(-100.0, min(100.0, right_speed)))

        command = f"M:{left_int},{right_int}\n"
        with self.lock:
            try:
                self.serial.write(command.encode("utf-8"))
                self.serial.flush()
                logging.debug("Sent serial motor command: %s", command.strip())

                # Empty the incoming buffer to receive diagnostic logging/ACK from ESP32
                while self.serial.in_waiting > 0:
                    line = self.serial.readline().decode("utf-8", errors="ignore").strip()
                    if line:
                        logging.debug("ESP32: %s", line)
                        if "WARNING" in line or "ERR" in line:
                            logging.warning("ESP32 Warning/Error reported: %s", line)
            except Exception as exc:
                logging.error("Failed to transmit serial speed commands: %s", exc)
                self._handle_disconnection()

    def _handle_disconnection(self) -> None:
        logging.warning("Closing serial port due to communication failure...")
        try:
            if self.serial and self.serial.is_open:
                self.serial.close()
        except Exception:
            pass
        self.serial = None

    def stop(self) -> None:
        self.set_speeds(0.0, 0.0)

    def cleanup(self) -> None:
        logging.info("Cleaning up SerialMotorDriver...")
        try:
            self.stop()
            time.sleep(0.05)
            if self.serial and self.serial.is_open:
                self.serial.close()
                logging.info("Serial connection closed cleanly.")
        except Exception as e:
            logging.error("Error during serial driver cleanup: %s", e)
        finally:
            self.serial = None


class MPU6050:
    """
    High-level driver for MPU6050 6-Axis Motion Tracking I2C sensor.
    Uses integration over yaw gyro output (Z-axis) to estimate relative headings.
    """
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
        """
        Wakes up the sensor, configures gyro full-scale range and filtering.
        """
        try:
            self.bus.write_byte_data(self.address, self.PWR_MGMT_1, 0x00)
            self.bus.write_byte_data(self.address, self.GYRO_CONFIG, 0x08)  # +/- 500 deg/s
            self.bus.write_byte_data(self.address, self.CONFIG, 0x04)  # 21 Hz low-pass filter
            time.sleep(0.1)
            self.calibrate()
            self.ready = True
            logging.info("MPU6050 IMU successfully initialized.")
        except Exception as exc:
            logging.exception("Failed to communicate with MPU6050 during setup")
            raise OSError("MPU6050 initialization failed.") from exc

    def read_s16(self, register: int) -> int:
        """
        Reads a signed 16-bit word from a specified register.
        """
        high = self.bus.read_byte_data(self.address, register)
        low = self.bus.read_byte_data(self.address, register + 1)
        value = (high << 8) | low
        return value - 65536 if value & 0x8000 else value

    def read_gyro_z_deg_per_sec(self) -> float:
        """
        Queries Z gyro register and scales values to degrees per second.
        """
        return self.read_s16(self.GYRO_ZOUT_H) / 65.5  # Sensitivity scale factor for +/- 500 deg/s

    def calibrate(self) -> None:
        """
        Samples stationary gyro Z drift to establish a calibration bias offset.
        """
        samples = max(1, self.sensor_config.gyro_calibration_samples)
        logging.info("Calibrating MPU6050 gyro (sampling %d cycles)... Keep rover still.", samples)
        total = 0.0
        for _ in range(samples):
            try:
                total += self.read_gyro_z_deg_per_sec()
            except OSError:
                pass
            time.sleep(0.005)
        self.gyro_z_bias = total / samples
        self.yaw_deg = 0.0
        self.last_update = time.monotonic()
        logging.info("Gyro Z Calibration completed. Bias offset: %.3f deg/s", self.gyro_z_bias)

    def update(self) -> None:
        """
        Integrates gyro velocity over delta time to compute estimated yaw change.
        """
        if not self.ready:
            return

        try:
            now = time.monotonic()
            dt = now - self.last_update
            self.last_update = now
            gyro_z = self.read_gyro_z_deg_per_sec() - self.gyro_z_bias
            if abs(gyro_z) < self.sensor_config.gyro_deadband_deg_per_sec:
                gyro_z = 0.0
            self.yaw_deg = normalize_angle_degrees(self.yaw_deg + gyro_z * dt)
        except OSError:
            logging.debug("MPU6050 update failed. Skipping reading slice.")


class HMC5883L:
    """
    Driver for GY-271 / HMC5883L 3-Axis Magnetometer.
    Computes absolute orientation headings using earth magnetic fields.
    """
    def __init__(self, bus: Any, address: int, declination_deg: float) -> None:
        self.bus = bus
        self.address = address
        self.declination_deg = declination_deg
        self.ready = False

    def setup(self) -> None:
        """
        Configures sample averaging, gain settings, and sets operating mode.
        """
        try:
            self.bus.write_byte_data(self.address, 0x00, 0x70)  # 8-sample avg, 15 Hz default
            self.bus.write_byte_data(self.address, 0x01, 0x20)  # Gain setting
            self.bus.write_byte_data(self.address, 0x02, 0x00)  # Continuous-measurement mode
            self.ready = True
            logging.info("GY-271/HMC5883L Compass initialized.")
        except Exception as exc:
            logging.exception("Failed to initialize HMC5883L compass")
            raise OSError("HMC5883L Compass setup failed.") from exc

    def read_s16_pair(self, high_register: int) -> int:
        high = self.bus.read_byte_data(self.address, high_register)
        low = self.bus.read_byte_data(self.address, high_register + 1)
        value = (high << 8) | low
        return value - 65536 if value & 0x8000 else value

    def heading(self) -> float | None:
        """
        Calculates magnetic azimuth, applies magnetic declination offset,
        and returns heading degrees in [0, 360).
        """
        if not self.ready:
            return None

        try:
            x = self.read_s16_pair(0x03)
            y = self.read_s16_pair(0x07)
            heading = math.degrees(math.atan2(y, x)) + self.declination_deg
            return normalize_heading_degrees(heading)
        except OSError:
            logging.debug("HMC5883L compass read failed.")
            return None


class UltrasonicSensor:
    """
    Driver for HC-SR04 ultrasonic range finder sensor using high-precision
    monotomic clock measurements of GPIO pin transits.
    """
    def __init__(self, gpio: Any, trig_pin: int, echo_pin: int) -> None:
        self.gpio = gpio
        self.trig_pin = trig_pin
        self.echo_pin = echo_pin

    def setup(self) -> None:
        try:
            self.gpio.setup(self.trig_pin, self.gpio.OUT)
            self.gpio.setup(self.echo_pin, self.gpio.IN)
            self.gpio.output(self.trig_pin, False)
            time.sleep(0.05)
        except Exception as exc:
            logging.error("Failed to setup HC-SR04 GPIO: %s", exc)
            raise RuntimeError("Ultrasonic GPIO setup error.") from exc

    def distance_cm(self) -> float:
        """
        Triggers ultrasonic sensor burst and measures pulse width to compute distance.
        @return Obstacle distance in centimeters, or -1.0 if timeout occurred.
        """
        try:
            # Clear trigger pin
            self.gpio.output(self.trig_pin, False)
            time.sleep(0.000002)
            # Assert 10us trigger pulse
            self.gpio.output(self.trig_pin, True)
            time.sleep(0.00001)
            self.gpio.output(self.trig_pin, False)

            # Wait for Echo pin to rise
            deadline = time.monotonic() + 0.03
            while self.gpio.input(self.echo_pin) == 0:
                if time.monotonic() > deadline:
                    return -1.0
            pulse_start = time.monotonic()

            # Wait for Echo pin to fall
            deadline = time.monotonic() + 0.03
            while self.gpio.input(self.echo_pin) == 1:
                if time.monotonic() > deadline:
                    return -1.0
            pulse_end = time.monotonic()

            # Calculate distance using speed of sound (343 m/s)
            return (pulse_end - pulse_start) * 34300.0 / 2.0
        except Exception as e:
            logging.error("Error reading HC-SR04 distance: %s", e)
            return -1.0


class ServoScanner:
    """
    Drives an SG90 sweep servo to position the HC-SR04 sensor at angular offsets
    for generating sonar-like spatial distance map sweeps.
    """
    def __init__(self, gpio: Any, servo_pin: int, sensor: UltrasonicSensor, motion: MotionConfig) -> None:
        self.gpio = gpio
        self.servo_pin = servo_pin
        self.sensor = sensor
        self.motion = motion
        self.pwm: Any = None

    def setup(self) -> None:
        try:
            self.gpio.setup(self.servo_pin, self.gpio.OUT)
            self.pwm = self.gpio.PWM(self.servo_pin, 50)  # SG90 50 Hz PWM frequency
            self.pwm.start(0)
            self.write_angle(90)  # Face forward immediately
        except Exception as exc:
            logging.error("Failed to setup SG90 servo PWM: %s", exc)
            raise RuntimeError("Servo PWM initialization failed.") from exc

    def write_angle(self, angle: int) -> None:
        """
        Positions servo to specific angle between 0 and 180 degrees.
        """
        if self.pwm is None:
            return
        angle = max(0, min(180, angle))
        duty_cycle = 2.5 + angle / 18.0  # standard mapping to 0.5ms - 2.5ms pulse widths
        try:
            self.pwm.ChangeDutyCycle(duty_cycle)
            time.sleep(0.05)
            self.pwm.ChangeDutyCycle(0)  # Stop sending signal pulse to avoid servo jitter
        except Exception as exc:
            logging.error("Failed to command servo: %s", exc)

    def scan(self) -> list[dict[str, float]]:
        """
        Performs sweeping sonar sweep of environment and centers forward again.
        """
        readings = []
        for angle in range(0, 181, self.motion.scan_step_deg):
            self.write_angle(angle)
            time.sleep(self.motion.scan_settle_seconds)
            readings.append({"angle": float(angle), "distance": self.sensor.distance_cm()})
        self.write_angle(90)  # Return to forward position
        return readings

    def cleanup(self) -> None:
        logging.info("Cleaning up SG90 sweep servo...")
        if self.pwm is not None:
            try:
                self.pwm.stop()
            except Exception:
                pass
            self.pwm = None


class RealRoverHardware(HardwareBase):
    """
    Bridges all physical hardware drivers, configuring them per user configurations
    and handling cascading runtime errors gracefully.
    """
    def __init__(self, config: RoverConfig) -> None:
        self.config = config
        self.gpio: Any = None
        self.bus: Any = None
        self.motors: MotorDriver | SerialMotorDriver | None = None
        self.imu: MPU6050 | None = None
        self.compass: HMC5883L | None = None
        self.ultrasonic: UltrasonicSensor | None = None
        self.scanner: ServoScanner | None = None

    def setup(self) -> None:
        """
        Initializes Raspberry Pi physical interfaces and sub-drivers.
        """
        try:
            import RPi.GPIO as GPIO
        except ImportError:
            logging.warning(
                "RPi.GPIO is unavailable; GPIO motors, ultrasonic sensor, and scanner servo will be disabled. "
                "Camera streaming and object detection can still run."
            )
            GPIO = None

        self.gpio = GPIO
        if GPIO is not None:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)

        # 1. Configure Motors (either ESP32 Serial delegated or direct Pi GPIO)
        if self.config.hardware.esp32_serial_control:
            self.motors = SerialMotorDriver(
                self.config.hardware.esp32_serial_port,
                self.config.hardware.esp32_baudrate
            )
            try:
                self.motors.setup()
            except Exception:
                logging.exception("ESP32-S3 serial motor controller unavailable; continuing without motor output.")
                self.motors = None
        elif self.config.hardware.direct_motor_control:
            if GPIO is None:
                logging.warning("Direct motor control requested, but GPIO is unavailable; continuing without motor output.")
            else:
                self.motors = MotorDriver(GPIO, self.config.pins, self.config.hardware.motor_driver)
                try:
                    self.motors.setup()
                except Exception:
                    logging.exception("Direct GPIO motor driver unavailable; continuing without motor output.")
                    self.motors = None
        else:
            logging.warning("Motor drivers disabled in configuration; speeds will be ignored.")

        # 2. Configure I2C Sensors
        self._setup_i2c()

        # 3. Configure Sonar sweeps
        self._setup_scanner()

    def _setup_i2c(self) -> None:
        if not self.config.hardware.i2c_enabled:
            logging.info("I2C sensors disabled by config.")
            return

        try:
            from smbus2 import SMBus
        except ImportError:
            logging.warning("smbus2 is not installed; MPU6050 and HMC5883L compass disabled.")
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
                logging.exception("MPU6050 sensor not found on I2C bus; heading tracking disabled.")
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
                logging.exception("HMC5883L compass sensor not found on I2C bus; compass disabled.")
                self.compass = None

    def _setup_scanner(self) -> None:
        if not self.config.hardware.ultrasonic_enabled:
            logging.info("Ultrasonic sensor disabled by config.")
            return

        if self.gpio is None:
            logging.warning("GPIO interface unavailable. Cannot initialize HC-SR04.")
            return

        self.ultrasonic = UltrasonicSensor(
            self.gpio,
            self.config.pins.ultrasonic_trig,
            self.config.pins.ultrasonic_echo,
        )
        try:
            self.ultrasonic.setup()
        except Exception:
            logging.exception("Failed to configure Ultrasonic rangefinder.")
            self.ultrasonic = None
            return

        if not self.config.hardware.scanner_servo_enabled:
            logging.info("Scanner servo sweeping disabled by config.")
            return

        self.scanner = ServoScanner(
            self.gpio,
            self.config.pins.scanner_servo,
            self.ultrasonic,
            self.config.motion,
        )
        try:
            self.scanner.setup()
        except Exception:
            logging.exception("Failed to configure SG90 scanner servo.")
            self.scanner = None

    def update(self) -> None:
        """
        Invoked periodically by the main loops to run heading calculations.
        """
        if self.imu is not None:
            try:
                self.imu.update()
            except OSError:
                logging.exception("MPU6050 read failure during update; disabling IMU.")
                self.imu = None

    def read_heading(self) -> float | None:
        """
        Checks available heading telemetry. Prefers Compass, falls back to integrated IMU yaw.
        """
        if self.compass is not None:
            try:
                heading = self.compass.heading()
                if heading is not None:
                    return heading
            except OSError:
                logging.exception("Compass read error; disabling compass sensor.")
                self.compass = None

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
        """
        Performs safe teardown of motor PWM, close serial links, and resets GPIO.
        """
        logging.info("Shutting down physical hardware devices...")
        if self.motors is not None:
            try:
                self.motors.cleanup()
            except Exception:
                pass
        if self.scanner is not None:
            try:
                self.scanner.cleanup()
            except Exception:
                pass
        if self.bus is not None:
            try:
                self.bus.close()
            except Exception:
                pass
        if self.gpio is not None:
            try:
                self.gpio.cleanup()
            except Exception:
                pass
        logging.info("Hardware teardown complete.")


class RoverClient:
    """
    Main Thread supervisor managing remote communications, telemetry transmissions,
    and delegating navigational command packets.
    """
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
        self.mode = MODE_IDLE
        self.mode_lock = threading.Lock()
        self.latest_follow_target: dict[str, Any] | None = None
        self.last_follow_target_at = 0.0
        self.follow_thread: threading.Thread | None = None

    @property
    def websocket_url(self) -> str:
        return f"ws://{self.config.server_host}:{self.config.server_port}{self.config.websocket_path}"

    def send_json(self, payload: dict[str, Any]) -> None:
        """
        Safely serializes and sends JSON messages over the WebSocket link.
        """
        if not self.connected.is_set() or self.ws is None:
            return
        message = json.dumps(payload, separators=(",", ":"))
        with self.send_lock:
            try:
                self.ws.send(message)
            except Exception as exc:
                logging.error("Failed to transmit WebSocket message: %s", exc)
                self.connected.clear()

    def set_mode(self, mode: str, message: str = "") -> None:
        with self.mode_lock:
            self.mode = mode
        self.send_json({"status": mode.lower(), "mode": mode, "message": message})

    def get_mode(self) -> str:
        with self.mode_lock:
            return self.mode

    def on_open(self, ws: websocket.WebSocketApp) -> None:
        logging.info("WebSocket handshake successful. Connected to %s", self.websocket_url)
        self.connected.set()
        # Identity registration packet
        self.send_json({"id": self.config.rover_id, "type": ROVER_TYPE})
        self.send_json({"status": "ready"})

    def on_close(self, ws: websocket.WebSocketApp, status_code: int, message: str) -> None:
        logging.warning("WebSocket link severed: Status: %s - %s", status_code, message)
        self.connected.clear()
        self.hardware.stop_motors()

    def on_error(self, ws: websocket.WebSocketApp, error: Exception) -> None:
        logging.warning("WebSocket exception occurred: %s", error)

    def on_message(self, ws: websocket.WebSocketApp, message: str) -> None:
        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            logging.warning("Received invalid non-JSON telemetry packet: %s", message)
            return

        if isinstance(payload, dict) and payload.get("cmd") == "stop":
            # Interrupt active operations instantly
            logging.info("Received immediate EMERGENCY STOP directive from server.")
            self.movement_cancel.set()
            self.hardware.stop_motors()
            self.set_mode(MODE_EMERGENCY_STOP, "Emergency stop requested")
        elif isinstance(payload, dict) and payload.get("type") == "vision_result":
            self.handle_vision_result(payload)
        elif isinstance(payload, dict) and "cmd" in payload:
            logging.debug("Enqueued command packet: %s", payload.get("cmd"))
            self.command_queue.put(payload)
        else:
            logging.debug("Non-executable server dispatch: %s", payload)

    def camera_loop(self) -> None:
        camera = self.config.camera
        if not camera.enabled:
            logging.info("Raspberry Pi webcam streaming disabled by config.")
            return

        try:
            import cv2
        except ImportError:
            logging.error("opencv-python is required for Pi webcam streaming. Install rover/rpi2b requirements.")
            return

        while not self.stop_requested.is_set():
            cap = cv2.VideoCapture(camera.index)
            if not cap.isOpened():
                logging.warning("Could not open Raspberry Pi webcam index %s; retrying.", camera.index)
                time.sleep(3)
                continue

            cap.set(cv2.CAP_PROP_FRAME_WIDTH, camera.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, camera.height)
            cap.set(cv2.CAP_PROP_FPS, camera.fps)
            logging.info(
                "Streaming Raspberry Pi webcam index %s to Windows server at %sx%s.",
                camera.index,
                camera.width,
                camera.height,
            )

            while not self.stop_requested.is_set():
                ok, frame = cap.read()
                if not ok or frame is None:
                    logging.warning("Pi webcam read failed; reconnecting camera.")
                    break

                if self.connected.is_set():
                    quality = max(30, min(95, int(camera.jpeg_quality)))
                    encoded_ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
                    if encoded_ok:
                        self.send_json(
                            {
                                "type": "camera_frame",
                                "format": "jpeg",
                                "image_b64": base64.b64encode(encoded.tobytes()).decode("ascii"),
                                "width": int(frame.shape[1]),
                                "height": int(frame.shape[0]),
                                "captured_at": time.time(),
                            }
                        )

                time.sleep(max(0.1, float(camera.upload_interval_seconds)))

            cap.release()
            time.sleep(1)

    def handle_vision_result(self, payload: dict[str, Any]) -> None:
        if not payload.get("detected"):
            return

        category = str(payload.get("category") or "event").lower()
        message = str(payload.get("message") or "Activity detected.")
        action = "alert"

        if category == "human":
            self.latest_follow_target = payload
            self.last_follow_target_at = time.monotonic()
            if self.get_mode() == MODE_FOLLOW:
                action = "follow_update"
            else:
                self.movement_cancel.set()
                self.hardware.stop_motors()
                action = "stop_and_alert"
                self.set_mode(MODE_WAITING_DECISION, "human detected; waiting for dashboard decision")
        elif category == "fire":
            self.movement_cancel.set()
            self.hardware.stop_motors()
            action = "stop_and_alert"
            self.set_mode(MODE_WAITING_DECISION, "fire detected; waiting for dashboard decision")
        elif category == "marker":
            action = "remember_marker"

        self.send_json(
            {
                "type": "vision_decision",
                "detected": True,
                "category": category,
                "message": message,
                "action": action,
                "alert": True,
                "marker": payload.get("marker", ""),
                "image_path": payload.get("image_path", ""),
                "x": payload.get("x", 400.0),
                "y": payload.get("y", 400.0),
                "heading": payload.get("heading", self.last_heading),
                "label": payload.get("label", ""),
                "box": payload.get("box", {}),
                "frame_width": payload.get("frame_width", payload.get("width", 0)),
                "frame_height": payload.get("frame_height", payload.get("height", 0)),
                "guidance": payload.get("guidance", {}),
                "mode": self.get_mode(),
            }
        )

    def telemetry_loop(self) -> None:
        """
        Fires periodic state telemetry reports and keeps the connection active.
        """
        last_heartbeat = 0.0
        last_telemetry = 0.0
        while not self.stop_requested.is_set():
            now = time.monotonic()
            self.hardware.update()

            heading = self.hardware.read_heading()
            if heading is not None:
                self.last_heading = heading

            # 1. Periodically transmit heading and spatial movement metrics
            if now - last_telemetry >= self.config.motion.telemetry_interval_seconds:
                last_telemetry = now
                self.send_json(
                    {
                        "heading": self.last_heading,
                        "distance_traveled": self.distance_traveled_cm,
                        "mode": self.get_mode(),
                    }
                )

            # 2. Periodically transmit server status heartbeats
            if now - last_heartbeat >= self.config.motion.heartbeat_interval_seconds:
                last_heartbeat = now
                self.send_json({"status": "ready"})

            time.sleep(0.02)

    def command_loop(self) -> None:
        """
        Pulls command packets from queue and dispatches execution targets sequentially.
        """
        while not self.stop_requested.is_set():
            try:
                command = self.command_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                logging.info("Executing commanded task: %s", command.get("cmd"))
                self.handle_command(command)
            except Exception:
                logging.exception("Exception occurred during commanded execution block")
                self.hardware.stop_motors()
                self.send_json({"status": "command_error"})

    def handle_command(self, command: dict[str, Any]) -> None:
        """
        Handles routing and execution of enqueued commands.
        """
        cmd = command.get("cmd")
        if cmd == "goto":
            self.set_mode(MODE_MANUAL, "Manual map goal accepted")
            self.handle_goto(float(command.get("angle", 0.0)), float(command.get("distance", 0.0)))
        elif cmd == "scan":
            report: dict[str, Any] = {"type": "scan", "data": self.hardware.scan()}
            if command.get("target"):
                report["target"] = str(command["target"])
            self.send_json(report)
        elif cmd == "stop":
            self.movement_cancel.set()
            self.hardware.stop_motors()
            self.set_mode(MODE_EMERGENCY_STOP, "Stopped by dashboard")
        elif cmd == "follow":
            self.start_follow_mode()
        elif cmd == "stay_stopped":
            self.movement_cancel.set()
            self.hardware.stop_motors()
            self.set_mode(MODE_WAITING_DECISION, "Staying stopped")
        elif cmd == "resume_patrol":
            self.movement_cancel.clear()
            self.hardware.stop_motors()
            self.set_mode(MODE_PATROL, "Patrol resumed")
        else:
            logging.warning("Unrecognized routing target requested: %s", command)

    def start_follow_mode(self) -> None:
        if self.latest_follow_target is None:
            self.hardware.stop_motors()
            self.set_mode(MODE_WAITING_DECISION, "No human target available to follow")
            return
        self.movement_cancel.clear()
        self.set_mode(MODE_FOLLOW, "Following human target")
        if self.follow_thread is None or not self.follow_thread.is_alive():
            self.follow_thread = threading.Thread(target=self.follow_loop, name="follow-loop", daemon=True)
            self.follow_thread.start()

    def follow_loop(self) -> None:
        motion = self.config.motion
        while not self.stop_requested.is_set() and self.get_mode() == MODE_FOLLOW:
            if time.monotonic() - self.last_follow_target_at > motion.follow_lost_timeout_seconds:
                self.hardware.stop_motors()
                self.set_mode(MODE_WAITING_DECISION, "Follow target lost")
                break
            target = self.latest_follow_target or {}
            box = target.get("box") if isinstance(target.get("box"), dict) else {}
            frame_width = float(target.get("frame_width") or target.get("width") or 640)
            frame_height = float(target.get("frame_height") or target.get("height") or 480)
            box_width = float(box.get("width", 0) or 0)
            box_height = float(box.get("height", 0) or 0)
            if box_width <= 0 or box_height <= 0:
                self.hardware.stop_motors()
                time.sleep(motion.follow_update_interval_seconds)
                continue
            front_distance = self.hardware.front_distance_cm()
            if front_distance is not None and front_distance <= self.config.hardware.obstacle_stop_distance_cm:
                self.movement_cancel.set()
                self.hardware.stop_motors()
                self.set_mode(MODE_EMERGENCY_STOP, f"Obstacle at {front_distance:.0f} cm")
                break
            center_x = float(box.get("x", 0) or 0) + box_width / 2.0
            center_error = (center_x - frame_width / 2.0) / max(1.0, frame_width / 2.0)
            area_ratio = (box_width * box_height) / max(1.0, frame_width * frame_height)
            forward = motion.follow_base_pwm if area_ratio < motion.follow_target_area_ratio else 0.0
            turn = 0.0 if abs(center_error) < motion.follow_deadband_ratio else center_error * motion.follow_turn_pwm
            left_speed = max(-motion.turn_max_pwm, min(motion.turn_max_pwm, forward + turn))
            right_speed = max(-motion.turn_max_pwm, min(motion.turn_max_pwm, forward - turn))
            self.hardware.set_motors(left_speed, right_speed)
            time.sleep(motion.follow_update_interval_seconds)
        self.hardware.stop_motors()

    def handle_goto(self, angle: float, distance_cm: float) -> None:
        """
        Closed-loop navigator that coordinates turning towards target azimuth,
        followed by driving straight for a given distance while checking for obstacles.
        """
        self.movement_cancel.clear()
        heading = self.hardware.read_heading()
        
        if heading is None and self.config.hardware.require_heading_for_goto:
            logging.error("IMU/Compass headings missing! Rejecting Goto command.")
            self.hardware.stop_motors()
            self.send_json(
                {
                    "status": "imu_error",
                    "message": "No heading source available and require_heading_for_goto is enabled",
                }
            )
            return

        # 1. Adjust orientation heading
        if heading is None:
            # Fallback to open-loop timed turn
            logging.warning("Compass/IMU readings absent. Executing timed open-loop alignment.")
            self.open_loop_turn_to_angle(angle)
        else:
            self.last_heading = heading
            logging.info("Executing closed-loop PID alignment to target: %.1f deg", angle)
            self.turn_to_angle(angle)

        time.sleep(0.1)  # Settling buffer delay
        
        # 2. Advance forward safely
        drive_status = "goal_reached"
        if not self.movement_cancel.is_set():
            logging.info("Driving forward %.1f cm...", distance_cm)
            drive_status = self.drive_forward(distance_cm)
            
        if self.movement_cancel.is_set():
            drive_status = "stopped"
            
        self.send_json({"status": drive_status})

    def turn_to_angle(self, target_angle: float) -> None:
        """
        Closed-loop PID turning loop. Drives differential motors to match target heading.
        """
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
                logging.error("Lost heading feedback midpoint of turning. Aborting turn.")
                break
            
            self.last_heading = heading
            error = normalize_angle_degrees(target_angle - heading)
            
            # Escape criteria
            if abs(error) <= motion.turn_tolerance_deg:
                logging.info("PID turning target reached. Margin error: %.2f deg.", error)
                break

            # Calculate proportional power
            speed = max(motion.turn_min_pwm, min(motion.turn_max_pwm, abs(error) * motion.turn_kp))
            if error > 0:
                self.hardware.set_motors(speed, -speed)
            else:
                self.hardware.set_motors(-speed, speed)
            time.sleep(0.01)

        self.hardware.stop_motors()

    def open_loop_turn_to_angle(self, target_angle: float) -> None:
        """
        Fallback open-loop turning method based on time estimations.
        """
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
        """
        Drives forward, continuously checking ultrasonic sensor for obstacles.
        """
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
            
            # Periodically poll obstacle avoidance scanner
            if now - last_obstacle_check >= self.config.hardware.obstacle_check_interval_seconds:
                last_obstacle_check = now
                front_distance = self.hardware.front_distance_cm()
                if (
                    front_distance is not None
                    and front_distance <= self.config.hardware.obstacle_stop_distance_cm
                ):
                    logging.warning(
                        "Obstacle detected at %.1f cm! Executing emergency stop.", 
                        front_distance
                    )
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
        """
        Clean signal handler triggered by termination events (SIGINT, SIGTERM).
        """
        logging.info("RoverClient termination request received. Safely stopping motors.")
        self.stop_requested.set()
        self.movement_cancel.set()
        self.connected.clear()
        self.hardware.stop_motors()
        if self.ws is not None:
            try:
                self.ws.close()
            except Exception:
                pass

    def run(self) -> None:
        """
        Initializes hardware hooks, spawns command & telemetry loops, and starts
        the blocking WebSocket auto-reconnect cycle.
        """
        try:
            self.hardware.setup()
        except Exception as exc:
            logging.exception("Fatal error setting up rover client hardware components")
            return

        # Start communication supervisor threads
        threading.Thread(target=self.command_loop, name="command-loop", daemon=True).start()
        threading.Thread(target=self.telemetry_loop, name="telemetry-loop", daemon=True).start()
        threading.Thread(target=self.camera_loop, name="pi-camera-loop", daemon=True).start()

        # Connect / reconnect loop
        while not self.stop_requested.is_set():
            logging.info("Initiating connection to server %s as %s", self.websocket_url, self.config.rover_id)
            self.ws = websocket.WebSocketApp(
                self.websocket_url,
                on_open=self.on_open,
                on_close=self.on_close,
                on_error=self.on_error,
                on_message=self.on_message,
            )
            try:
                self.ws.run_forever(ping_interval=15, ping_timeout=3)
            except Exception as e:
                logging.error("WebSocket run_forever experienced an exception: %s", e)
            
            self.connected.clear()
            self.hardware.stop_motors()
            
            # Wait briefly before attempting reconnect
            if not self.stop_requested.is_set():
                time.sleep(3)

        self.hardware.cleanup()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="STASIS Raspberry Pi rover client")
    parser.add_argument("--config", type=Path, default=Path("config.json"))
    parser.add_argument("--server", help="Laptop/server IP or hostname running Flask on port 5000")
    parser.add_argument("--port", type=int, help="Server WebSocket port")
    parser.add_argument("--rover-id", help="Rover client id expected by the server")
    parser.add_argument("--simulate", action="store_true", help="Run without physical sensor interfaces")
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=args.log_level.upper(), format="%(asctime)s %(levelname)s %(message)s")
    
    # Read config file safely
    config = read_config(args.config)

    # Command line overrides
    if args.server:
        config.server_host = args.server
    if args.port:
        config.server_port = args.port
    if args.rover_id:
        config.rover_id = args.rover_id
    if args.simulate:
        config.simulate = True

    if not config.server_host:
        raise SystemExit("STASIS server host ip is unspecified. Use config.json or specify via --server <IP>.")

    # Select hardware implementation
    hardware: HardwareBase = SimulatedHardware(config) if config.simulate else RealRoverHardware(config)
    client = RoverClient(config, hardware)
    
    # Register termination signals for graceful stopping
    signal.signal(signal.SIGINT, client.request_stop)
    signal.signal(signal.SIGTERM, client.request_stop)
    
    try:
        client.run()
    except Exception as exc:
        logging.critical("Stasis rover client terminated with a fatal exception: %s", exc)
    finally:
        logging.info("Stasis client session terminated safely.")


if __name__ == "__main__":
    main()

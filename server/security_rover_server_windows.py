"""
STASIS Forest Monitoring Rover - Central Control Server (Windows)

This module implements the central Flask and Socket.IO control server,
typically executed on a laptop/workstation. It provides the following services:
1. Web Dashboard: Host a real-time web control dashboard (HTML/JS/CSS).
2. Rover Telemetry Hub: WebSocket endpoints for real-time telemetry registration 
   (IMU headings, distance logs, ultrasonic scanning data, and active goals).
3. Vision Analytics: Captures local webcam feed, pipelines images into local Gemma 
   VLMs to detect fire, smoke, intruders, wildlife, or colored navigational markers,
   and dispatches real-time web notifications.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Generator, Dict, List, Optional, Union

import cv2
import torch
from flask import Flask, render_template, request, send_from_directory, Response
from flask_socketio import SocketIO, emit
from PIL import Image
from simple_websocket import ConnectionClosed, Server
from transformers import pipeline

# ==========================================
# FILE PATHS & WORKSPACE DEFINITIONS
# ==========================================
BASE_DIR: Path = Path(__file__).resolve().parent
ALERTS_DIR: Path = BASE_DIR / "alerts"

# ==========================================
# ENV LOADING HELPERS (With safe fallbacks)
# ==========================================
def env_bool(name: str, default: bool) -> bool:
    """
    Parses environment variable values to boolean options.
    """
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_float(name: str, default: float) -> float:
    """
    Parses environment variables to floats, falling back to defaults on errors.
    """
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        logging.warning("Invalid float env %s=%r; falling back to %.2f", name, value, default)
        return default


def env_int(name: str, default: int) -> int:
    """
    Parses environment variables to integers, falling back to defaults on errors.
    """
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        logging.warning("Invalid int env %s=%r; falling back to %d", name, value, default)
        return default


# ==========================================
# GLOBAL SYSTEM CONFIGURATIONS
# ==========================================
VISION_ENABLED: bool = env_bool("STASIS_VISION_ENABLED", True)
VISION_REQUIRED: bool = env_bool("STASIS_VISION_REQUIRED", False)
VISION_MODEL: str = os.getenv("STASIS_VISION_MODEL", "google/gemma-4-E2B-it")
VISION_PIPELINE_TASK: str = os.getenv("STASIS_VISION_PIPELINE_TASK", "any-to-any")
VISION_DEVICE: str = os.getenv("STASIS_VISION_DEVICE", "auto")
VISION_DEVICE_MAP: str = os.getenv("STASIS_VISION_DEVICE_MAP", "auto")
VISION_TORCH_DTYPE: str = os.getenv("STASIS_VISION_TORCH_DTYPE", "auto")
VISION_MAX_NEW_TOKENS: int = env_int("STASIS_VISION_MAX_NEW_TOKENS", 160)
ANALYSIS_INTERVAL_SECONDS: float = env_float("STASIS_ANALYSIS_INTERVAL_SECONDS", 2.0)

CAMERA_INDEX: int = env_int("STASIS_CAMERA_INDEX", 0)
CAMERA_WIDTH: int = env_int("STASIS_CAMERA_WIDTH", 640)
CAMERA_HEIGHT: int = env_int("STASIS_CAMERA_HEIGHT", 480)
CAMERA_FPS: int = env_int("STASIS_CAMERA_FPS", 15)
CAMERA_BACKEND: str = os.getenv("STASIS_CAMERA_BACKEND", "dshow")

PIXEL_TO_CM: float = 1.0  # Mapping scale constant: pixels in UI to physical cm
ROVER_CLIENT_ID: str = "rpi2b_rover"
ALLOWED_EVENT_CATEGORIES: set[str] = {"human", "animal", "track", "fire", "marker"}

# Lexicon mappings used to ensure Gemma alert relevance to the Stasis project
PROJECT_KEYWORDS: set[str] = {
    "human", "person", "people", "intruder", "animal", "wildlife", "track", 
    "trail", "footprint", "soil", "disturbed", "fire", "flame", "smoke", 
    "marker", "strip"
}
MARKER_COLORS: set[str] = {"red", "blue", "green", "yellow", "orange", "white", "black"}

DEFAULT_ANALYSIS_PROMPT: str = (
    "Analyze this STASIS forest-monitoring rover frame. Look for humans or intruders, "
    "animals or wildlife stand-ins, soil differences, footprints, trails, disturbed ground, "
    "fire, smoke, flame, and custom colored navigation markers such as red strips. "
    "Respond with exactly one JSON object and no Markdown. Use this schema: "
    "{\"detected\": boolean, \"category\": \"human|animal|track|fire|marker\", "
    "\"message\": string}. Set detected to true only when a relevant STASIS monitoring event or "
    "marker is visible. Intruders are category human. Use category marker for colored strips. "
    "Keep message short and specific; use an empty string when detected is false."
)
ANALYSIS_PROMPT: str = os.getenv("STASIS_ANALYSIS_PROMPT", DEFAULT_ANALYSIS_PROMPT)

# ==========================================
# FLASK & INTERFACE REGISTRATIONS
# ==========================================
app: Flask = Flask(__name__, template_folder=str(BASE_DIR / "templates"))
socketio: SocketIO = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Shared state variables accessed across threads
latest_frame: Optional[Any] = None
vision_pipe: Optional[Any] = None

rover_ws: Optional[Server] = None
rover_socketio_sid: Optional[str] = None

home_position: Dict[str, float] = {"x": 400.0, "y": 400.0}
home_heading: Optional[float] = None
last_distance_traveled: Optional[float] = None
latest_scan: List[Dict[str, float]] = []

rover_pose: Dict[str, float] = {
    "x": 400.0,
    "y": 400.0,
    "yaw": 0.0,
    "heading": 0.0,
    "distance_from_home": 0.0
}
pending_goal: Optional[Dict[str, float]] = None
known_markers: Dict[str, Dict[str, Any]] = {}


def get_camera_backend() -> int:
    """
    Resolves OpenCV camera backend strings to functional constants.
    """
    backend = CAMERA_BACKEND.strip().lower()
    if backend in {"", "auto", "default", "none"}:
        return 0
    if backend == "dshow":
        return cv2.CAP_DSHOW
    if backend == "msmf":
        return cv2.CAP_MSMF
    logging.warning("Unknown backend: %r; falling back to default.", CAMERA_BACKEND)
    return 0


def get_vision_device() -> str:
    """
    Detects hardware resources, prioritizing CUDA acceleration over CPU defaults.
    """
    if VISION_DEVICE.lower() != "auto":
        return VISION_DEVICE
    return "cuda" if torch.cuda.is_available() else "cpu"


def get_vision_dtype(device: str) -> torch.dtype:
    """
    Resolves tensor data types matching selected execution hardware.
    """
    dtype_name = VISION_TORCH_DTYPE.lower()
    if dtype_name == "auto":
        return torch.bfloat16 if device.startswith("cuda") else torch.float32

    dtype_by_name = {
        "bfloat16": torch.bfloat16,
        "float16": torch.float16,
        "float32": torch.float32,
    }
    if dtype_name not in dtype_by_name:
        logging.warning("Invalid dtype configuration %r; choosing auto", VISION_TORCH_DTYPE)
        return torch.bfloat16 if device.startswith("cuda") else torch.float32
    return dtype_by_name[dtype_name]


def get_vision_device_map() -> Optional[str]:
    """
    Extracts custom model distribution topologies.
    """
    value = VISION_DEVICE_MAP.strip()
    if value.lower() in {"", "none", "false", "off"}:
        return None
    return value


def build_pipeline_kwargs() -> Dict[str, Any]:
    """
    Prepares argument mappings for HuggingFace pipeline constructors.
    """
    device_map = get_vision_device_map()
    if device_map is not None:
        return {
            "model": VISION_MODEL,
            "device_map": device_map,
            "dtype": VISION_TORCH_DTYPE,
        }

    device = get_vision_device()
    return {
        "model": VISION_MODEL,
        "device": device,
        "torch_dtype": get_vision_dtype(device),
    }


def load_vision_model() -> None:
    """
    Loads VLM pipeline. Tolerates initial model loading failures cleanly.
    """
    global vision_pipe

    if not VISION_ENABLED:
        logging.warning("Vision model analysis is deactivated by user configs.")
        return

    pipeline_kwargs = build_pipeline_kwargs()
    logging.info(
        "Loading VLM model %s on task: %s...",
        VISION_MODEL,
        VISION_PIPELINE_TASK
    )

    load_error: Optional[Exception] = None
    try:
        vision_pipe = pipeline(VISION_PIPELINE_TASK, **pipeline_kwargs)
        logging.info("VLM Model pipeline loaded successfully.")
    except TypeError as error:
        load_error = error
        # Attempt fallback to alternative torch_dtype parameter format
        if "dtype" in pipeline_kwargs:
            fallback_kwargs = dict(pipeline_kwargs)
            fallback_kwargs.pop("dtype")
            fallback_kwargs["torch_dtype"] = get_vision_dtype(get_vision_device())
            logging.warning("Retrying Gemma initialization using 'torch_dtype' keys...")
            try:
                vision_pipe = pipeline(VISION_PIPELINE_TASK, **fallback_kwargs)
                load_error = None
                logging.info("VLM Model pipeline loaded via fallback arguments.")
            except Exception as fallback_error:
                load_error = fallback_error
    except Exception as error:
        load_error = error

    if load_error is not None:
        logging.error("Failed to load Gemma vision model pipeline: %s", load_error, exc_info=True)
        if VISION_REQUIRED:
            raise load_error
        logging.warning("Continuing server startup without Vision alerting services.")
        vision_pipe = None


def webcam_capture_loop() -> None:
    """
    Background worker loop continuously capturing frames from the configured video camera.
    """
    global latest_frame

    while True:
        try:
            backend = get_camera_backend()
            cap = cv2.VideoCapture(CAMERA_INDEX, backend) if backend else cv2.VideoCapture(CAMERA_INDEX)
            if not cap.isOpened():
                logging.warning("Failed to open camera device at index %d. Retrying...", CAMERA_INDEX)
                time.sleep(3)
                continue

            cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
            cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
            logging.info(
                "Connected to local video capture source at index %d (%dx%d@%d FPS)",
                CAMERA_INDEX, CAMERA_WIDTH, CAMERA_HEIGHT, CAMERA_FPS
            )

            while True:
                try:
                    ok, frame = cap.read()
                    if not ok or frame is None:
                        logging.warning("Webcam capture read cycle returned empty frame.")
                        break
                    latest_frame = frame.copy()
                except Exception as read_err:
                    logging.error("Exception during live camera buffer read: %s", read_err)
                    break
                # Micro-sleep to respect requested frame intervals
                time.sleep(1.0 / max(1, CAMERA_FPS))

            cap.release()
        except Exception as loop_err:
            logging.error("Webcam capture worker loop encountered an error: %s. Restarting...", loop_err)
        time.sleep(2)


def frame_to_pil(frame: Any) -> Image.Image:
    """
    Converts raw OpenCV BGR arrays to standard RGB PIL images.
    """
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb_frame)


def extract_model_text(model_output: Any) -> str:
    """
    Recursively unwraps pipeline text return schemas into flat strings.
    """
    if isinstance(model_output, str):
        return model_output

    if isinstance(model_output, list) and model_output:
        for item in reversed(model_output):
            text = extract_model_text(item)
            if text:
                return text
        return ""

    if isinstance(model_output, dict):
        for key in ("content", "generated_text", "caption", "text", "answer"):
            value = model_output.get(key)
            if value is not None:
                return extract_model_text(value)

    return str(model_output)


def parse_json_response(text: str) -> Dict[str, Any]:
    """
    Decodes and cleanses JSON response objects returned by VLM models,
    cross-referencing labels against allowed classifications and keywords.
    """
    stripped = text.strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        parsed = extract_json_object(stripped)

    if not isinstance(parsed, dict):
        raise ValueError(f"Vision model response parsed to {type(parsed).__name__}, expected dictionary.")

    detected_value = parsed.get("detected", False)
    detected = detected_value.strip().lower() == "true" if isinstance(detected_value, str) else bool(detected_value)
    message = str(parsed.get("message", "")).strip()

    if not detected:
        return {"detected": False, "category": "", "message": ""}

    category = normalize_event_category(parsed.get("category"), message)
    if category not in ALLOWED_EVENT_CATEGORIES:
        logging.info("Suppressing out-of-scope Gemma detection: category=%r message=%r", category, message)
        return {"detected": False, "category": "", "message": ""}

    message = normalize_event_message(category, message)
    if not message_has_project_context(message):
        logging.info("Suppressing detection lack of project context: %r", message)
        return {"detected": False, "category": "", "message": ""}

    return {
        "detected": True,
        "category": category,
        "message": message[:500],
        "marker": extract_marker_name(message) if category == "marker" else "",
    }


def normalize_event_category(category_value: Any, message: str) -> str:
    """
    Maps loose VLM classifications to system taxonomy classes.
    """
    category = str(category_value or "").strip().lower()
    category = category.split(":", 1)[0].strip()
    if category in ALLOWED_EVENT_CATEGORIES:
        return category

    lowered = message.lower().strip()
    prefix = lowered.split(":", 1)[0].strip()
    if prefix in ALLOWED_EVENT_CATEGORIES:
        return prefix

    keyword_categories = {
        "human": ("human", "person", "people", "intruder"),
        "animal": ("animal", "wildlife", "dog", "cat", "bird"),
        "track": ("track", "trail", "footprint", "soil", "disturbed"),
        "fire": ("fire", "flame", "smoke"),
        "marker": ("marker", "strip"),
    }
    for candidate, keywords in keyword_categories.items():
        if any(keyword in lowered for keyword in keywords):
            return candidate
    return ""


def normalize_event_message(category: str, message: str) -> str:
    """
    Enforces unified labeling prefixes on logging alerts.
    """
    message = " ".join(message.split())
    if not message:
        return ""

    lowered = message.lower()
    if lowered.startswith(f"{category}:"):
        return f"{category}: {message.split(':', 1)[1].strip()}"
    return f"{category}: {message}"


def message_has_project_context(message: str) -> bool:
    """
    Checks if VLM text responses reference core Stasis domain keywords.
    """
    lowered = message.lower()
    return any(keyword in lowered for keyword in PROJECT_KEYWORDS)


def extract_marker_name(message: str) -> str:
    """
    Identifies color identifiers within marker labels.
    """
    lowered = message.lower()
    for color in MARKER_COLORS:
        if color in lowered and ("strip" in lowered or "marker" in lowered):
            return f"{color}_strip"
    if "strip" in lowered or "marker" in lowered:
        return "unknown_marker"
    return ""


def extract_json_object(text: str) -> Dict[str, Any]:
    """
    Slices raw text blocks to extract contained JSON strings.
    """
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            parsed, _end = decoder.raw_decode(text[match.start() :])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise ValueError("Text contains no parsable JSON object segments.")


def build_vision_messages(image: Image.Image) -> List[Dict[str, Any]]:
    """
    Formats multi-modal user prompts compatible with HF ChatTemplates.
    """
    return [
        {
            "role": "system",
            "content": [
                {
                    "type": "text",
                    "text": "You are the STASIS rover vision module. Output strict JSON only.",
                }
            ],
        },
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": ANALYSIS_PROMPT},
            ],
        },
    ]


def analyze_frame(frame: Any) -> Dict[str, Any]:
    """
    Invokes the pipeline to process a raw frame.
    """
    if vision_pipe is None:
        return {"detected": False, "message": ""}

    image = frame_to_pil(frame)
    try:
        result = vision_pipe(
            text=build_vision_messages(image),
            return_full_text=False,
            generate_kwargs={"max_new_tokens": VISION_MAX_NEW_TOKENS, "do_sample": False},
        )
    except TypeError:
        # Backward compatibility for models not supporting generate_kwargs
        result = vision_pipe(
            text=build_vision_messages(image),
            return_full_text=False,
            max_new_tokens=VISION_MAX_NEW_TOKENS,
        )

    return parse_json_response(extract_model_text(result))


def save_alert_frame(frame: Any) -> str:
    """
    Persists alert snapshots to disk under the alerts subdirectory.
    """
    ALERTS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"alert_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg"
    image_path = ALERTS_DIR / filename

    if not cv2.imwrite(str(image_path), frame):
        raise RuntimeError(f"Could not write alert snapshot to destination: {image_path}")

    return f"alerts/{filename}"


def camera_mjpeg_stream() -> Generator[bytes, None, None]:
    """
    Generates Motion-JPEG multipart camera feeds for web client streaming.
    """
    while True:
        frame = latest_frame
        if frame is None:
            time.sleep(0.1)
            continue

        ok, encoded = cv2.imencode(".jpg", frame)
        if not ok:
            time.sleep(0.1)
            continue

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + encoded.tobytes()
            + b"\r\n"
        )
        time.sleep(1.0 / max(1, CAMERA_FPS))


def send_rover_command(command: Dict[str, Any]) -> bool:
    """
    Transmits a command structure to the connected physical rover via WebSocket or Socket.IO.
    
    @return True if transmitted successfully, otherwise False.
    """
    global rover_ws

    if rover_ws is not None:
        try:
            rover_ws.send(json.dumps(command))
            logging.info("Dispatched websocket command to rover: %s", command)
            return True
        except ConnectionClosed:
            rover_ws = None

    if rover_socketio_sid is not None:
        try:
            socketio.emit("rover_command", command, to=rover_socketio_sid)
            logging.info("Dispatched SocketIO command to rover: %s", command)
            return True
        except Exception as exc:
            logging.error("Failed sending SocketIO command: %s", exc)

    logging.warning("Command drop: No rover client connection registered. Command: %s", command)
    return False


def is_rover_client(client_id: Optional[str]) -> bool:
    return client_id == ROVER_CLIENT_ID


def vision_analysis_loop() -> None:
    """
    Periodic background loop evaluating captured camera buffers for security detections.
    """
    while True:
        try:
            time.sleep(ANALYSIS_INTERVAL_SECONDS)
            if not VISION_ENABLED or vision_pipe is None:
                continue
            if latest_frame is None:
                continue

            frame = latest_frame.copy()
            try:
                analysis = analyze_frame(frame)
            except Exception as analysis_err:
                logging.error("Exception during VLM frame classification: %s", analysis_err)
                continue

            if not analysis["detected"]:
                continue

            # Event triggered, capture snapshot and notify web clients
            try:
                image_path = save_alert_frame(frame)
            except Exception as save_err:
                logging.error("Failed saving alert snapshot file: %s", save_err)
                image_path = ""

            payload = {
                "category": analysis["category"],
                "message": analysis["message"],
                "image_path": image_path,
            }
            if analysis.get("marker"):
                payload["marker"] = analysis["marker"]
                remember_marker(analysis["marker"], image_path)

            logging.info("ALERT DISPATCHED: Category=%s Message=%s", analysis["category"], analysis["message"])
            socketio.emit("new_alert", payload)
        except Exception as loop_err:
            logging.error("Vision analytics thread encountered a catastrophic exception: %s", loop_err)


def normalize_angle_degrees(angle: float) -> float:
    while angle > 180.0:
        angle -= 360.0
    while angle < -180.0:
        angle += 360.0
    return angle


def normalize_heading_degrees(angle: float) -> float:
    return angle % 360.0


def update_distance_from_home() -> None:
    """
    Recalculates straight-line distance offset from home origin point.
    """
    dx = rover_pose["x"] - home_position["x"]
    dy = rover_pose["y"] - home_position["y"]
    rover_pose["distance_from_home"] = math.sqrt(dx**2 + dy**2) * PIXEL_TO_CM


def build_goto_command(target_x: float, target_y: float) -> Dict[str, Any]:
    """
    Computes required relative turning angles and distances to steer rover 
    towards coordinates target_x, target_y on the map dashboard.
    """
    dx = target_x - rover_pose["x"]
    dy = target_y - rover_pose["y"]
    map_angle_to_goal = math.degrees(math.atan2(dy, dx))
    angle_to_goal = normalize_heading_degrees((home_heading or 0.0) + map_angle_to_goal)
    distance_cm = math.sqrt(dx**2 + dy**2) * PIXEL_TO_CM
    return {"cmd": "goto", "angle": angle_to_goal, "distance": distance_cm}


def remember_marker(marker_name: str, image_path: str) -> None:
    """
    Records a detected navigational marker's coordinates.
    """
    if not marker_name:
        return
    known_markers[marker_name] = {
        "name": marker_name,
        "x": rover_pose["x"],
        "y": rover_pose["y"],
        "heading": rover_pose["heading"],
        "image_path": image_path,
        "seen_at": datetime.now().isoformat(timespec="seconds"),
    }
    socketio.emit("marker_seen", known_markers[marker_name])


def handle_rover_telemetry(payload: Dict[str, Any]) -> None:
    """
    Parses and integrates periodic navigation telemetry updates into the dashboard state map.
    """
    global home_heading, last_distance_traveled

    try:
        heading = float(payload["heading"])
        distance_traveled = float(payload["distance_traveled"])
    except (KeyError, TypeError, ValueError):
        return

    # Use first reported heading telemetry as alignment origin zero frame
    if home_heading is None:
        home_heading = heading
        last_distance_traveled = distance_traveled

    previous_distance = last_distance_traveled if last_distance_traveled is not None else distance_traveled
    distance_delta = max(0.0, distance_traveled - previous_distance)
    last_distance_traveled = distance_traveled

    map_yaw = normalize_angle_degrees(heading - home_heading)
    rover_pose["heading"] = normalize_heading_degrees(heading)
    rover_pose["yaw"] = map_yaw

    if distance_delta > 0.0:
        yaw_rad = math.radians(map_yaw)
        rover_pose["x"] += math.cos(yaw_rad) * (distance_delta / PIXEL_TO_CM)
        rover_pose["y"] += math.sin(yaw_rad) * (distance_delta / PIXEL_TO_CM)

    update_distance_from_home()
    socketio.emit("rover_position", rover_pose.copy())


def handle_scan_report(payload: Dict[str, Any]) -> None:
    """
    Validates enqueued HC-SR04 sweeping sonar reports.
    """
    global latest_scan

    scan_data = payload.get("data", [])
    if not isinstance(scan_data, list):
        return

    latest_scan = []
    for point in scan_data:
        if not isinstance(point, dict):
            continue
        try:
            latest_scan.append({"angle": float(point["angle"]), "distance": float(point["distance"])})
        except (KeyError, TypeError, ValueError):
            continue

    socketio.emit("scan_data", {"data": latest_scan})


def handle_rover_report(payload: Any) -> None:
    """
    Validates, handles, and routes all raw message structures arriving from the rover.
    """
    global pending_goal

    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return

    if not isinstance(payload, dict):
        return

    # Parse telemetry updates
    if "heading" in payload and "distance_traveled" in payload:
        handle_rover_telemetry(payload)

    # Parse sweeping sensor reports
    if payload.get("type") == "scan":
        handle_scan_report(payload)

    # Propagate status reports
    status = payload.get("status")
    if isinstance(status, str):
        socketio.emit("rover_status", {"status": status, "message": payload.get("message", "")})
        if status in {"stopped", "obstacle_detected", "imu_error", "command_error"}:
            pending_goal = None

    # Sync goal positions on successful navigation completion
    if payload.get("status") == "goal_reached":
        if pending_goal is not None:
            rover_pose["x"] = pending_goal["x"]
            rover_pose["y"] = pending_goal["y"]
            pending_goal = None

        update_distance_from_home()
        socketio.emit("rover_position", rover_pose.copy())


# ==========================================
# FLASK HTTP ROUTING HANDLERS
# ==========================================
@app.route("/")
def index() -> str:
    """
    Serves the main monitoring dashboard layout.
    """
    return render_template("index.html")


@app.route("/alerts/<path:filename>")
def serve_alert(filename: str) -> Response:
    """
    Serves captured vision snapshot images.
    """
    return send_from_directory(str(ALERTS_DIR), filename)


@app.route("/camera.mjpg")
def camera_feed() -> Response:
    """
    Streams camera video blocks continuously.
    """
    return app.response_class(camera_mjpeg_stream(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/ws/rover", websocket=True)
def rover_websocket() -> str:
    """
    Primary low-overhead TCP WebSocket endpoint providing duplex transport 
    for Raspberry Pi rover telemetries and control dispatches.
    """
    global rover_ws

    ws = Server.accept(request.environ)
    client_id = request.args.get("id") or request.args.get("client_id")
    initial_payload = None

    if client_id is None:
        try:
            initial_payload = json.loads(ws.receive())
            client_id = initial_payload.get("id")
        except (ConnectionClosed, json.JSONDecodeError, AttributeError, TypeError):
            ws.close()
            return ""

    if not is_rover_client(client_id):
        ws.send(json.dumps({"error": "unknown_client"}))
        ws.close()
        return ""

    rover_ws = ws
    ws.send(json.dumps({"status": "registered", "id": client_id}))
    logging.info("Rover client register successful: websocket ID=%s", client_id)

    if initial_payload is not None:
        handle_rover_report(initial_payload)

    try:
        while True:
            raw_msg = ws.receive()
            if raw_msg is None:
                break
            handle_rover_report(raw_msg)
    except ConnectionClosed:
        logging.warning("Rover client WebSocket connection lost.")
    finally:
        if rover_ws is ws:
            rover_ws = None

    return ""


# ==========================================
# SOCKETIO REMOTE TELEMETRY HANDLERS
# ==========================================
@socketio.on("connect")
def on_connect(auth: Optional[Dict[str, Any]] = None) -> None:
    """
    Invoked when web dashboard users or SocketIO clients open links.
    """
    global rover_socketio_sid

    client_id = None
    if isinstance(auth, dict):
        client_id = auth.get("id") or auth.get("client_id")
    client_id = client_id or request.args.get("id") or request.args.get("client_id")

    if is_rover_client(client_id):
        rover_socketio_sid = request.sid
        logging.info("Rover registered over SocketIO connection: SID=%s", request.sid)
        emit("rover_registered", {"id": client_id})
        return

    # Direct sync dashboards with current posing stats
    emit("rover_position", rover_pose.copy())
    emit("scan_data", {"data": latest_scan})


@socketio.on("disconnect")
def on_disconnect() -> None:
    """
    Cleans socket registration states when clients sever links.
    """
    global rover_socketio_sid
    if request.sid == rover_socketio_sid:
        logging.warning("Rover SocketIO link severed.")
        rover_socketio_sid = None


@socketio.on("set_goal")
def on_set_goal(payload: Dict[str, Any]) -> None:
    """
    Sets coordinate navigation goals for the rover.
    """
    global pending_goal

    try:
        target_x = float(payload["x"])
        target_y = float(payload["y"])
    except (KeyError, TypeError, ValueError):
        emit("goal_error", {"message": "Goal payloads must define numeric x and y parameters."})
        return

    pending_goal = {"x": target_x, "y": target_y}
    command = build_goto_command(target_x, target_y)
    sent = send_rover_command(command)
    if not sent:
        pending_goal = None
    emit("goal_commanded", {"sent": sent, "command": command})


@socketio.on("return_home")
def on_return_home() -> None:
    """
    Commands the rover to steer and drive back to home coordinates.
    """
    global pending_goal

    pending_goal = home_position.copy()
    command = build_goto_command(home_position["x"], home_position["y"])
    sent = send_rover_command(command)
    if not sent:
        pending_goal = None
    emit("goal_commanded", {"sent": sent, "command": command})


@socketio.on("request_scan")
def on_request_scan() -> None:
    """
    Triggers ultrasonic sweep commands to the rover.
    """
    sent = send_rover_command({"cmd": "scan"})
    emit("scan_requested", {"sent": sent})


@socketio.on("search_marker")
def on_search_marker(payload: Optional[Dict[str, Any]] = None) -> None:
    """
    Dispatches targeted scan directives to look for specific visual markers.
    """
    marker = "red_strip"
    if isinstance(payload, dict):
        marker = str(payload.get("marker") or marker).strip().lower().replace(" ", "_")
    sent = send_rover_command({"cmd": "scan", "target": marker})
    emit("marker_search_started", {"sent": sent, "marker": marker})


@socketio.on("go_to_marker")
def on_go_to_marker(payload: Optional[Dict[str, Any]] = None) -> None:
    """
    Directs the rover to drive to the coordinates of a previously saved marker.
    """
    global pending_goal

    marker = "red_strip"
    if isinstance(payload, dict):
        marker = str(payload.get("marker") or marker).strip().lower().replace(" ", "_")

    target = known_markers.get(marker)
    if target is None:
        emit("marker_error", {"marker": marker, "message": "The specified marker has not been seen yet."})
        return

    pending_goal = {"x": target["x"], "y": target["y"]}
    command = build_goto_command(target["x"], target["y"])
    sent = send_rover_command(command)
    if not sent:
        pending_goal = None
    emit("marker_goal_commanded", {"sent": sent, "marker": marker, "command": command})


@socketio.on("stop_rover")
def on_stop_rover() -> None:
    """
    Dispatches immediate halt commands to the rover.
    """
    sent = send_rover_command({"cmd": "stop"})
    emit("stop_requested", {"sent": sent})


@socketio.on("rover_status")
def on_rover_status(payload: Any) -> None:
    handle_rover_report(payload)


@socketio.on("message")
def on_message(payload: Any) -> None:
    handle_rover_report(payload)


# ==========================================
# SYSTEM RUNENTRY HANDLER
# ==========================================
def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    
    # Assert destination structures exist
    ALERTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load neural models
    load_vision_model()
    
    # Start concurrent threads for hardware capturing and visual processing
    socketio.start_background_task(webcam_capture_loop)
    socketio.start_background_task(vision_analysis_loop)
    
    # Execute Flask SocketIO webserver
    logging.info("Starting STASIS Flask-SocketIO central webserver on 0.0.0.0:5000...")
    socketio.run(app, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    main()

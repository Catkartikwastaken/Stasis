from __future__ import annotations

import json
import logging
import math
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import torch
from flask import Flask, render_template, request, send_from_directory
from flask_socketio import SocketIO, emit
from PIL import Image
from simple_websocket import ConnectionClosed, Server
from transformers import pipeline


BASE_DIR = Path(__file__).resolve().parent
ALERTS_DIR = BASE_DIR / "alerts"


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        logging.warning("Invalid %s=%r; using %.2f", name, value, default)
        return default


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        logging.warning("Invalid %s=%r; using %d", name, value, default)
        return default


VISION_ENABLED = env_bool("STASIS_VISION_ENABLED", True)
VISION_REQUIRED = env_bool("STASIS_VISION_REQUIRED", False)
VISION_MODEL = os.getenv("STASIS_VISION_MODEL", "google/gemma-4-E2B-it")
VISION_PIPELINE_TASK = os.getenv("STASIS_VISION_PIPELINE_TASK", "any-to-any")
VISION_DEVICE = os.getenv("STASIS_VISION_DEVICE", "auto")
VISION_DEVICE_MAP = os.getenv("STASIS_VISION_DEVICE_MAP", "auto")
VISION_TORCH_DTYPE = os.getenv("STASIS_VISION_TORCH_DTYPE", "auto")
VISION_MAX_NEW_TOKENS = env_int("STASIS_VISION_MAX_NEW_TOKENS", 160)
ANALYSIS_INTERVAL_SECONDS = env_float("STASIS_ANALYSIS_INTERVAL_SECONDS", 2.0)
CAMERA_INDEX = env_int("STASIS_CAMERA_INDEX", 0)
CAMERA_WIDTH = env_int("STASIS_CAMERA_WIDTH", 640)
CAMERA_HEIGHT = env_int("STASIS_CAMERA_HEIGHT", 480)
CAMERA_FPS = env_int("STASIS_CAMERA_FPS", 15)
CAMERA_BACKEND = os.getenv("STASIS_CAMERA_BACKEND", "dshow")
PIXEL_TO_CM = 1.0
ROVER_CLIENT_ID = "rpi2b_rover"
ALLOWED_EVENT_CATEGORIES = {"human", "animal", "track", "fire", "marker"}
PROJECT_KEYWORDS = {
    "human",
    "person",
    "people",
    "intruder",
    "animal",
    "wildlife",
    "track",
    "trail",
    "footprint",
    "soil",
    "disturbed",
    "fire",
    "flame",
    "smoke",
    "marker",
    "strip",
}
MARKER_COLORS = {"red", "blue", "green", "yellow", "orange", "white", "black"}

DEFAULT_ANALYSIS_PROMPT = (
    "Analyze this STASIS forest-monitoring rover frame. The demo may be indoors, but the scene is "
    "staged like a forest patrol area. Look for humans or intruders, animals or wildlife stand-ins, "
    "soil differences, footprints, trails, disturbed ground, fire, smoke, flame, and custom colored "
    "navigation markers such as red strips. Ignore ordinary indoor doors and windows unless they are "
    "relevant to the demo. "
    "Respond with exactly one JSON object and no Markdown. Use this schema: "
    "{\"detected\": boolean, \"category\": \"human|animal|track|fire|marker\", "
    "\"message\": string}. Set detected to true only when a relevant STASIS monitoring event or "
    "marker is visible. Intruders are category human. Use category marker for colored strips. "
    "Keep message short and specific; use an empty string when detected is false."
)
ANALYSIS_PROMPT = os.getenv("STASIS_ANALYSIS_PROMPT", DEFAULT_ANALYSIS_PROMPT)

app = Flask(__name__, template_folder=str(BASE_DIR / "templates"))
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

latest_frame = None
vision_pipe = None

rover_ws: Server | None = None
rover_socketio_sid: str | None = None
home_position = {"x": 400.0, "y": 400.0}
home_heading: float | None = None
last_distance_traveled: float | None = None
latest_scan: list[dict[str, float]] = []
rover_pose = {"x": 400.0, "y": 400.0, "yaw": 0.0, "heading": 0.0, "distance_from_home": 0.0}
pending_goal: dict[str, float] | None = None
known_markers: dict[str, dict[str, Any]] = {}


def get_camera_backend() -> int:
    backend = CAMERA_BACKEND.strip().lower()
    if backend in {"", "auto", "default", "none"}:
        return 0
    if backend == "dshow":
        return cv2.CAP_DSHOW
    if backend == "msmf":
        return cv2.CAP_MSMF
    logging.warning("Unknown STASIS_CAMERA_BACKEND=%r; using default OpenCV backend", CAMERA_BACKEND)
    return 0


def get_vision_device() -> str:
    if VISION_DEVICE.lower() != "auto":
        return VISION_DEVICE
    return "cuda" if torch.cuda.is_available() else "cpu"


def get_vision_dtype(device: str) -> torch.dtype:
    dtype_name = VISION_TORCH_DTYPE.lower()
    if dtype_name == "auto":
        return torch.bfloat16 if device.startswith("cuda") else torch.float32

    dtype_by_name = {
        "bfloat16": torch.bfloat16,
        "float16": torch.float16,
        "float32": torch.float32,
    }
    if dtype_name not in dtype_by_name:
        logging.warning("Invalid STASIS_VISION_TORCH_DTYPE=%r; using auto", VISION_TORCH_DTYPE)
        return torch.bfloat16 if device.startswith("cuda") else torch.float32
    return dtype_by_name[dtype_name]


def get_vision_device_map() -> str | None:
    value = VISION_DEVICE_MAP.strip()
    if value.lower() in {"", "none", "false", "off"}:
        return None
    return value


def build_pipeline_kwargs() -> dict[str, Any]:
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
    global vision_pipe

    if not VISION_ENABLED:
        logging.warning("Gemma vision analysis is disabled with STASIS_VISION_ENABLED=false")
        return

    pipeline_kwargs = build_pipeline_kwargs()
    logging.info(
        "Loading Gemma vision model %s with task=%s options=%s",
        VISION_MODEL,
        VISION_PIPELINE_TASK,
        {key: value for key, value in pipeline_kwargs.items() if key != "model"},
    )

    load_error: Exception | None = None
    try:
        vision_pipe = pipeline(VISION_PIPELINE_TASK, **pipeline_kwargs)
    except TypeError as error:
        load_error = error
        if "dtype" in pipeline_kwargs:
            fallback_kwargs = dict(pipeline_kwargs)
            fallback_kwargs.pop("dtype")
            fallback_kwargs["torch_dtype"] = get_vision_dtype(get_vision_device())
            logging.warning("Retrying Gemma model load with torch_dtype instead of dtype")
            try:
                vision_pipe = pipeline(VISION_PIPELINE_TASK, **fallback_kwargs)
                load_error = None
            except Exception as fallback_error:
                load_error = fallback_error
    except Exception as error:
        load_error = error

    if load_error is not None:
        logging.error(
            "Could not load Gemma vision model",
            exc_info=(type(load_error), load_error, load_error.__traceback__),
        )
        if VISION_REQUIRED:
            raise load_error
        logging.warning("Continuing without vision alerts. Set STASIS_VISION_REQUIRED=true to fail fast.")
        vision_pipe = None


def webcam_capture_loop() -> None:
    global latest_frame

    while True:
        backend = get_camera_backend()
        cap = cv2.VideoCapture(CAMERA_INDEX, backend) if backend else cv2.VideoCapture(CAMERA_INDEX)
        if not cap.isOpened():
            logging.warning("Could not open webcam index %s", CAMERA_INDEX)
            time.sleep(3)
            continue

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
        cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
        logging.info(
            "Connected to webcam index %s at requested %sx%s@%sfps",
            CAMERA_INDEX,
            CAMERA_WIDTH,
            CAMERA_HEIGHT,
            CAMERA_FPS,
        )
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                logging.warning("Webcam read failed; reconnecting")
                break
            latest_frame = frame.copy()

        cap.release()
        time.sleep(1)


def frame_to_pil(frame) -> Image.Image:
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb_frame)


def extract_model_text(model_output: Any) -> str:
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


def parse_json_response(text: str) -> dict[str, Any]:
    stripped = text.strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        parsed = extract_json_object(stripped)

    if not isinstance(parsed, dict):
        raise ValueError(f"Vision model returned JSON {type(parsed).__name__}, expected object")

    detected_value = parsed.get("detected", False)
    detected = detected_value.strip().lower() == "true" if isinstance(detected_value, str) else bool(detected_value)
    message = str(parsed.get("message", "")).strip()
    if not detected:
        return {"detected": False, "category": "", "message": ""}

    category = normalize_event_category(parsed.get("category"), message)
    if category not in ALLOWED_EVENT_CATEGORIES:
        logging.info("Suppressing out-of-scope Gemma alert: category=%r message=%r", category, message)
        return {"detected": False, "category": "", "message": ""}

    message = normalize_event_message(category, message)
    if not message_has_project_context(message):
        logging.info("Suppressing alert without STASIS project context: %r", message)
        return {"detected": False, "category": "", "message": ""}

    return {
        "detected": True,
        "category": category,
        "message": message[:500],
        "marker": extract_marker_name(message) if category == "marker" else "",
    }


def normalize_event_category(category_value: Any, message: str) -> str:
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
    message = " ".join(message.split())
    if not message:
        return ""

    lowered = message.lower()
    if lowered.startswith(f"{category}:"):
        return f"{category}: {message.split(':', 1)[1].strip()}"
    return f"{category}: {message}"


def message_has_project_context(message: str) -> bool:
    lowered = message.lower()
    return any(keyword in lowered for keyword in PROJECT_KEYWORDS)


def extract_marker_name(message: str) -> str:
    lowered = message.lower()
    for color in MARKER_COLORS:
        if color in lowered and ("strip" in lowered or "marker" in lowered):
            return f"{color}_strip"
    if "strip" in lowered or "marker" in lowered:
        return "unknown_marker"
    return ""


def extract_json_object(text: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            parsed, _end = decoder.raw_decode(text[match.start() :])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise ValueError(f"Vision model did not return a JSON object: {text[:200]}")


def build_vision_messages(image: Image.Image) -> list[dict[str, Any]]:
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


def analyze_frame(frame) -> dict[str, Any]:
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
        result = vision_pipe(
            text=build_vision_messages(image),
            return_full_text=False,
            max_new_tokens=VISION_MAX_NEW_TOKENS,
        )

    return parse_json_response(extract_model_text(result))


def save_alert_frame(frame) -> str:
    ALERTS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"alert_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg"
    image_path = ALERTS_DIR / filename

    if not cv2.imwrite(str(image_path), frame):
        raise RuntimeError(f"Could not write alert snapshot to {image_path}")

    return f"alerts/{filename}"


def camera_mjpeg_stream():
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
        time.sleep(1 / max(1, CAMERA_FPS))


def send_rover_command(command: dict[str, Any]) -> bool:
    global rover_ws

    if rover_ws is not None:
        try:
            rover_ws.send(json.dumps(command))
            return True
        except ConnectionClosed:
            rover_ws = None

    if rover_socketio_sid is not None:
        socketio.emit("rover_command", command, to=rover_socketio_sid)
        return True

    logging.warning("No rover is connected; command not sent: %s", command)
    return False


def is_rover_client(client_id: str | None) -> bool:
    return client_id == ROVER_CLIENT_ID


def vision_analysis_loop() -> None:
    while True:
        time.sleep(ANALYSIS_INTERVAL_SECONDS)
        if not VISION_ENABLED or vision_pipe is None:
            continue
        if latest_frame is None:
            continue

        frame = latest_frame.copy()
        try:
            analysis = analyze_frame(frame)
        except Exception:
            logging.exception("Vision analysis failed")
            continue

        if not analysis["detected"]:
            continue

        image_path = save_alert_frame(frame)
        payload = {
            "category": analysis["category"],
            "message": analysis["message"],
            "image_path": image_path,
            "x": rover_pose["x"],
            "y": rover_pose["y"],
            "heading": rover_pose["heading"],
        }
        if analysis.get("marker"):
            payload["marker"] = analysis["marker"]
            remember_marker(analysis["marker"], image_path)
        socketio.emit("new_alert", payload)
        # Physical sound hardware was removed; alerts now stay in the web dashboard.


def normalize_angle_degrees(angle: float) -> float:
    while angle > 180.0:
        angle -= 360.0
    while angle < -180.0:
        angle += 360.0
    return angle


def normalize_heading_degrees(angle: float) -> float:
    return angle % 360.0


def update_distance_from_home() -> None:
    dx = rover_pose["x"] - home_position["x"]
    dy = rover_pose["y"] - home_position["y"]
    rover_pose["distance_from_home"] = math.sqrt(dx**2 + dy**2) * PIXEL_TO_CM


def build_goto_command(target_x: float, target_y: float) -> dict[str, Any]:
    dx = target_x - rover_pose["x"]
    dy = target_y - rover_pose["y"]
    map_angle_to_goal = math.degrees(math.atan2(dy, dx))
    angle_to_goal = normalize_heading_degrees((home_heading or 0.0) + map_angle_to_goal)
    distance_cm = math.sqrt(dx**2 + dy**2) * PIXEL_TO_CM
    return {"cmd": "goto", "angle": angle_to_goal, "distance": distance_cm}


def remember_marker(marker_name: str, image_path: str) -> None:
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


def handle_rover_telemetry(payload: dict[str, Any]) -> None:
    global home_heading, last_distance_traveled

    try:
        heading = float(payload["heading"])
        distance_traveled = float(payload["distance_traveled"])
    except (KeyError, TypeError, ValueError):
        return

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


def handle_scan_report(payload: dict[str, Any]) -> None:
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
    global pending_goal

    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return

    if not isinstance(payload, dict):
        return

    if "heading" in payload and "distance_traveled" in payload:
        handle_rover_telemetry(payload)

    if payload.get("type") == "scan":
        handle_scan_report(payload)

    status = payload.get("status")
    if isinstance(status, str):
        socketio.emit("rover_status", {"status": status, "message": payload.get("message", "")})
        if status in {"stopped", "obstacle_detected", "imu_error", "command_error"}:
            pending_goal = None

    if payload.get("status") == "goal_reached":
        if pending_goal is not None:
            rover_pose["x"] = pending_goal["x"]
            rover_pose["y"] = pending_goal["y"]
            pending_goal = None

        update_distance_from_home()
        socketio.emit("rover_position", rover_pose.copy())


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/alerts/<path:filename>")
def serve_alert(filename: str):
    return send_from_directory(ALERTS_DIR, filename)


@app.route("/camera.mjpg")
def camera_feed():
    return app.response_class(camera_mjpeg_stream(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/ws/rover", websocket=True)
def rover_websocket():
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

    if initial_payload is not None:
        handle_rover_report(initial_payload)

    try:
        while True:
            handle_rover_report(ws.receive())
    except ConnectionClosed:
        if rover_ws is ws:
            rover_ws = None

    return ""


@socketio.on("connect")
def on_connect(auth=None):
    global rover_socketio_sid

    client_id = None
    if isinstance(auth, dict):
        client_id = auth.get("id") or auth.get("client_id")
    client_id = client_id or request.args.get("id") or request.args.get("client_id")

    if is_rover_client(client_id):
        rover_socketio_sid = request.sid
        emit("rover_registered", {"id": client_id})
        return

    emit("rover_position", rover_pose.copy())
    emit("scan_data", {"data": latest_scan})


@socketio.on("disconnect")
def on_disconnect():
    global rover_socketio_sid

    if request.sid == rover_socketio_sid:
        rover_socketio_sid = None


@socketio.on("set_goal")
def on_set_goal(payload):
    global pending_goal

    try:
        target_x = float(payload["x"])
        target_y = float(payload["y"])
    except (KeyError, TypeError, ValueError):
        emit("goal_error", {"message": "Goal payload must include numeric x and y"})
        return

    pending_goal = {"x": target_x, "y": target_y}
    command = build_goto_command(target_x, target_y)
    sent = send_rover_command(command)
    if not sent:
        pending_goal = None
    emit("goal_commanded", {"sent": sent, "command": command})


@socketio.on("return_home")
def on_return_home():
    global pending_goal

    pending_goal = home_position.copy()
    command = build_goto_command(home_position["x"], home_position["y"])
    sent = send_rover_command(command)
    if not sent:
        pending_goal = None
    emit("goal_commanded", {"sent": sent, "command": command})


@socketio.on("request_scan")
def on_request_scan():
    sent = send_rover_command({"cmd": "scan"})
    emit("scan_requested", {"sent": sent})


@socketio.on("search_marker")
def on_search_marker(payload=None):
    marker = "red_strip"
    if isinstance(payload, dict):
        marker = str(payload.get("marker") or marker).strip().lower().replace(" ", "_")
    sent = send_rover_command({"cmd": "scan", "target": marker})
    emit("marker_search_started", {"sent": sent, "marker": marker})


@socketio.on("go_to_marker")
def on_go_to_marker(payload=None):
    global pending_goal

    marker = "red_strip"
    if isinstance(payload, dict):
        marker = str(payload.get("marker") or marker).strip().lower().replace(" ", "_")

    target = known_markers.get(marker)
    if target is None:
        emit("marker_error", {"marker": marker, "message": "Marker has not been seen yet"})
        return

    pending_goal = {"x": target["x"], "y": target["y"]}
    command = build_goto_command(target["x"], target["y"])
    sent = send_rover_command(command)
    if not sent:
        pending_goal = None
    emit("marker_goal_commanded", {"sent": sent, "marker": marker, "command": command})


@socketio.on("stop_rover")
def on_stop_rover():
    sent = send_rover_command({"cmd": "stop"})
    emit("stop_requested", {"sent": sent})


@socketio.on("rover_status")
def on_rover_status(payload):
    handle_rover_report(payload)


@socketio.on("message")
def on_message(payload):
    handle_rover_report(payload)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ALERTS_DIR.mkdir(parents=True, exist_ok=True)
    load_vision_model()
    socketio.start_background_task(webcam_capture_loop)
    socketio.start_background_task(vision_analysis_loop)
    socketio.run(app, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    main()

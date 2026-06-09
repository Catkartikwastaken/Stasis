"""
STASIS Forest Monitoring Rover - Central Control Server (Windows)

This module implements the central Flask and Socket.IO control server,
typically executed on a laptop/workstation. It provides the following services:
1. Web Dashboard: Host a real-time web control dashboard (HTML/JS/CSS).
2. Rover Telemetry Hub: WebSocket endpoints for real-time telemetry registration 
   (IMU headings, distance logs, ultrasonic scanning data, and active goals).
3. Vision Analytics: Receives Raspberry Pi webcam frames, sends images to the
   configured multimodal provider, sends results back to the Pi for action
   decisions, and dispatches approved dashboard notifications.
"""

from __future__ import annotations

import base64
import json
import logging
import math
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Generator, Dict, List, Optional, Union

from flask import Flask, render_template, request, send_from_directory, Response
from flask_socketio import SocketIO, emit
from simple_websocket import ConnectionClosed, Server

DETECTOR_BACKEND = "none"
VISION_ENABLED = False

def detect(frame: Any) -> List[Dict[str, Any]]:
    if DETECTOR_BACKEND == "none":
        return []

    if DETECTOR_BACKEND == "custom":
        logging.warning("Custom detector backend not implemented in this milestone.")
        return []

    logging.warning("Unknown detector backend: %s", DETECTOR_BACKEND)
    return []

# ==========================================
# DETECTION POST-PROCESSING UTILITIES
# ==========================================
DETECTION_CONFIDENCE_THRESHOLD = 0.70
DETECTION_MIN_AREA_RATIO = 0.02

def normalize_detection(raw: Any) -> Optional[Dict[str, Any]]:
    """Validates raw dict structure and normalizes to standard schema."""
    if not isinstance(raw, dict):
        return None
    try:
        label = str(raw.get("label", "")).strip()
        confidence = float(raw.get("confidence", 0.0))
        bbox = raw.get("bbox")
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            return None
            
        x1, y1, x2, y2 = [float(c) for c in bbox]
        return {
            "label": label,
            "confidence": confidence,
            "bbox": [x1, y1, x2, y2]
        }
    except (ValueError, TypeError):
        return None

def filter_detection(detection: Dict[str, Any], frame_width: int, frame_height: int) -> tuple[bool, str]:
    """Filters out low-confidence, tiny, or malformed bounding boxes."""
    if frame_width <= 0 or frame_height <= 0:
        return False, "invalid_frame_dimensions"

    if not detection.get("label"):
        return False, "empty_label"
        
    if detection.get("confidence", 0.0) < DETECTION_CONFIDENCE_THRESHOLD:
        return False, "low_confidence"
        
    x1, y1, x2, y2 = detection.get("bbox", [0, 0, 0, 0])
    
    if x1 < 0 or y1 < 0 or x2 <= x1 or y2 <= y1:
        return False, "invalid_bbox"

    if x2 > frame_width or y2 > frame_height:
        return False, "bbox_outside_frame"
        
    bbox_area = (x2 - x1) * (y2 - y1)
    frame_area = frame_width * frame_height
    
    if bbox_area < (DETECTION_MIN_AREA_RATIO * frame_area):
        return False, "bbox_too_small"
        
    return True, "valid"

def postprocess_detections(detections: List[Any], frame_width: int, frame_height: int) -> List[Dict[str, Any]]:
    """Pipeline to normalize, filter, and log discarded detections."""
    valid_detections = []
    if not detections:
        return valid_detections
        
    for raw in detections:
        normalized = normalize_detection(raw)
        if not normalized:
            logging.debug("Detection rejected: malformed_data_structure")
            continue
            
        is_valid, reason = filter_detection(normalized, frame_width, frame_height)
        if is_valid:
            valid_detections.append(normalized)
        else:
            logging.debug("Detection rejected: %s", reason)
            
    return valid_detections

# ==========================================
# FILE PATHS & WORKSPACE DEFINITIONS
# ==========================================
BASE_DIR: Path = Path(__file__).resolve().parent
ALERTS_DIR: Path = BASE_DIR / "alerts"
VISION_CONFIG_PATH: Path = Path(os.getenv("STASIS_VISION_CONFIG", BASE_DIR / "vision_config.json"))

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
VISION_ENABLED: bool = env_bool("STASIS_VISION_ENABLED", False)
VISION_REQUIRED: bool = env_bool("STASIS_VISION_REQUIRED", False)
VISION_MODEL: str = os.getenv("STASIS_VISION_MODEL", "google/gemma-4-E2B-it")
VISION_PIPELINE_TASK: str = os.getenv("STASIS_VISION_PIPELINE_TASK", "any-to-any")
VISION_DEVICE: str = os.getenv("STASIS_VISION_DEVICE", "auto")
VISION_DEVICE_MAP: str = os.getenv("STASIS_VISION_DEVICE_MAP", "none")
VISION_TORCH_DTYPE: str = os.getenv("STASIS_VISION_TORCH_DTYPE", "auto")
VISION_MAX_NEW_TOKENS: int = env_int("STASIS_VISION_MAX_NEW_TOKENS", 160)
ANALYSIS_INTERVAL_SECONDS: float = env_float("STASIS_ANALYSIS_INTERVAL_SECONDS", 2.0)

CAMERA_INDEX: int = env_int("STASIS_CAMERA_INDEX", 0)
CAMERA_WIDTH: int = env_int("STASIS_CAMERA_WIDTH", 640)
CAMERA_HEIGHT: int = env_int("STASIS_CAMERA_HEIGHT", 480)
CAMERA_FPS: int = env_int("STASIS_CAMERA_FPS", 15)
CAMERA_BACKEND: str = os.getenv("STASIS_CAMERA_BACKEND", "dshow")
CAMERA_SOURCE: str = os.getenv("STASIS_CAMERA_SOURCE", "rover").strip().lower()

PIXEL_TO_CM: float = 1.0  # Mapping scale constant: pixels in UI to physical cm
ROVER_CLIENT_ID: str = "rpi2b_rover"
ALLOWED_EVENT_CATEGORIES: set[str] = {"human", "animal", "track", "fire", "marker"}

# Event Logging Config
EVENT_LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
EVENT_LOG_FILE = os.path.join(EVENT_LOG_DIR, "stasis_events.jsonl")
_last_log_times = {"camera_frame": 0.0, "telemetry": 0.0}

def append_event_log(event_type: str, payload_summary: Dict[str, Any]) -> None:
    try:
        os.makedirs(EVENT_LOG_DIR, exist_ok=True)
        now = time.time()
        
        if event_type == "camera_frame_received":
            if now - _last_log_times["camera_frame"] < 5.0:
                return
            _last_log_times["camera_frame"] = now
        elif event_type == "telemetry_update":
            if now - _last_log_times["telemetry"] < 2.0:
                return
            _last_log_times["telemetry"] = now

        entry = {
            "timestamp": now,
            "event_type": event_type,
            "payload": payload_summary
        }
        with open(EVENT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as exc:
        logging.error("Failed to write to event log: %s", exc)

# Lexicon mappings used to ensure vision alert relevance to the STASIS project
PROJECT_KEYWORDS: set[str] = {
    "human", "person", "people", "intruder", "animal", "wildlife", "track", 
    "trail", "footprint", "soil", "disturbed", "fire", "flame", "smoke", 
    "marker", "strip"
}
MARKER_COLORS: set[str] = {"red", "blue", "green", "yellow", "orange", "white", "black"}

DEFAULT_ANALYSIS_PROMPT: str = (
    "Analyze this STASIS forest-monitoring rover frame. Look for humans or intruders, "
    "animals or wildlife stand-ins, soil differences, footprints, trails, disturbed ground, "
    "fire, smoke, flame, and custom colored navigation markers such as green strips. "
    "Respond with exactly one JSON object and no Markdown. Use this schema: "
    "{\"detected\": boolean, \"category\": \"human|animal|track|fire|marker\", "
    "\"message\": string}. Set detected to true only when a relevant STASIS monitoring event or "
    "marker is visible. Intruders are category human. Use category marker for colored green strips. "
    "Keep message short and specific; use an empty string when detected is false."
)
ANALYSIS_PROMPT: str = os.getenv("STASIS_ANALYSIS_PROMPT", DEFAULT_ANALYSIS_PROMPT)


def load_vision_config() -> Dict[str, Any]:
    """
    Loads provider configuration without requiring code edits.
    """
    default_config: Dict[str, Any] = {
        "enabled": False,
        "provider_order": [],
        "max_output_tokens": VISION_MAX_NEW_TOKENS,
        "request_timeout_seconds": 45,
        "providers": {
            "local_gemma": {
                "type": "local_gemma",
                "enabled": False,
                "model": VISION_MODEL,
                "pipeline_task": VISION_PIPELINE_TASK,
            }
        },
    }

    if not VISION_CONFIG_PATH.exists():
        return default_config

    try:
        loaded = json.loads(VISION_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        logging.warning("Could not read vision config %s: %s", VISION_CONFIG_PATH, exc)
        return default_config

    if not isinstance(loaded, dict):
        logging.warning("Vision config must be a JSON object; using defaults.")
        return default_config

    merged = dict(default_config)
    merged.update({key: value for key, value in loaded.items() if key != "providers"})
    providers = dict(default_config["providers"])
    providers.update(loaded.get("providers", {}) if isinstance(loaded.get("providers"), dict) else {})
    merged["providers"] = providers
    return merged


VISION_CONFIG: Dict[str, Any] = load_vision_config()
VISION_PROVIDER_ORDER: List[str] = [
    str(provider) for provider in VISION_CONFIG.get("provider_order", [])
]
VISION_PROVIDERS: Dict[str, Any] = (
    VISION_CONFIG.get("providers", {}) if isinstance(VISION_CONFIG.get("providers"), dict) else {}
)
VISION_REQUEST_TIMEOUT: float = float(VISION_CONFIG.get("request_timeout_seconds", 45))
ANALYSIS_PROMPT = os.getenv("STASIS_ANALYSIS_PROMPT", str(VISION_CONFIG.get("prompt", ANALYSIS_PROMPT)))

# ==========================================
# FLASK & INTERFACE REGISTRATIONS
# ==========================================
app: Flask = Flask(__name__, template_folder=str(BASE_DIR / "templates"))
socketio: SocketIO = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Shared state variables accessed across threads
latest_frame: Optional[Any] = None
latest_frame_jpeg: Optional[bytes] = None
latest_frame_metadata: Dict[str, Any] = {}
vision_pipe: Optional[Any] = None

rover_ws: Optional[Server] = None
rover_socketio_sid: Optional[str] = None

home_position: Dict[str, float] = {"x": 400.0, "y": 400.0}
home_heading: Optional[float] = None
last_distance_traveled: Optional[float] = None
latest_scan: List[Dict[str, float]] = []
recent_detections: List[Dict[str, Any]] = []

rover_pose: Dict[str, float] = {
    "x": 400.0,
    "y": 400.0,
    "yaw": 0.0,
    "heading": 0.0,
    "distance_from_home": 0.0
}
pending_goal: Optional[Dict[str, float]] = None
known_markers: Dict[str, Dict[str, Any]] = {}
tracked_target: Optional[Dict[str, Any]] = None


def record_detection_event(item: Dict[str, Any], accepted: bool, reason: str) -> None:
    event = {
        "label": str(item.get("label") or item.get("category_hint") or "unknown"),
        "category": str(item.get("category_hint") or "unknown"),
        "confidence": item.get("confidence", 0),
        "accepted": accepted,
        "reason": reason,
        "seen_at": datetime.now().isoformat(timespec="seconds"),
    }
    recent_detections.append(event)
    del recent_detections[:-30]
    socketio.emit("detection_debug", {"detections": recent_detections})


def get_camera_backend() -> int:
    """
    Resolves OpenCV camera backend strings to functional constants.
    """
    import cv2
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
    import torch

    return "cuda" if torch.cuda.is_available() else "cpu"


def get_vision_dtype(device: str) -> Any:
    """
    Resolves tensor data types matching selected execution hardware.
    """
    import torch

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
            "model": get_provider_config("local_gemma").get("model", VISION_MODEL),
            "device_map": device_map,
            "dtype": VISION_TORCH_DTYPE,
        }

    device = get_vision_device()
    return {
        "model": get_provider_config("local_gemma").get("model", VISION_MODEL),
        "device": device,
        "torch_dtype": get_vision_dtype(device),
    }


def get_provider_config(name: str) -> Dict[str, Any]:
    config = VISION_PROVIDERS.get(name, {})
    return config if isinstance(config, dict) else {}


def provider_enabled(name: str, config: Dict[str, Any]) -> bool:
    if not VISION_CONFIG.get("enabled", VISION_ENABLED):
        return False
    if not config.get("enabled", False):
        return False
    key_env = str(config.get("api_key_env", "")).strip()
    if key_env and not os.getenv(key_env):
        logging.info("Skipping vision provider %s because %s is not set.", name, key_env)
        return False
    return True


def local_gemma_enabled() -> bool:
    for provider_name in VISION_PROVIDER_ORDER:
        config = get_provider_config(provider_name)
        if config.get("type") == "local_gemma" and provider_enabled(provider_name, config):
            return True
    return False


def load_vision_model() -> None:
    """
    Loads VLM pipeline. Tolerates initial model loading failures cleanly.
    """
    global vision_pipe

    if not VISION_CONFIG.get("enabled", VISION_ENABLED):
        logging.warning("Vision model analysis is deactivated by user configs.")
        return
    if not local_gemma_enabled():
        logging.info("Local Gemma is not enabled in vision_config; skipping Torch/Transformers load.")
        return

    pipeline_kwargs = build_pipeline_kwargs()
    logging.info(
        "Loading VLM model %s on task: %s...",
        pipeline_kwargs.get("model", VISION_MODEL),
        get_provider_config("local_gemma").get("pipeline_task", VISION_PIPELINE_TASK),
    )

    load_error: Optional[Exception] = None
    try:
        from transformers import pipeline

        vision_pipe = pipeline(
            str(get_provider_config("local_gemma").get("pipeline_task", VISION_PIPELINE_TASK)),
            **pipeline_kwargs,
        )
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
    global latest_frame, latest_frame_jpeg
    import cv2

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
                    ok_enc, encoded = cv2.imencode(".jpg", latest_frame)
                    if ok_enc:
                        latest_frame_jpeg = encoded.tobytes()
                except Exception as read_err:
                    logging.error("Exception during live camera buffer read: %s", read_err)
                    break
                # Micro-sleep to respect requested frame intervals
                time.sleep(1.0 / max(1, CAMERA_FPS))

            cap.release()
        except Exception as loop_err:
            logging.error("Webcam capture worker loop encountered an error: %s. Restarting...", loop_err)
        time.sleep(2)


def frame_to_pil(frame: Any) -> Any:
    """
    Converts raw OpenCV BGR arrays to standard RGB PIL images.
    """
    import cv2
    from PIL import Image
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
        try:
            parsed = extract_json_object(stripped)
        except ValueError:
            return parse_plain_text_detection(stripped)

    if not isinstance(parsed, dict):
        raise ValueError(f"Vision model response parsed to {type(parsed).__name__}, expected dictionary.")

    detected_value = parsed.get("detected", False)
    detected = detected_value.strip().lower() == "true" if isinstance(detected_value, str) else bool(detected_value)
    message = str(parsed.get("message", "")).strip()

    if not detected:
        return {"detected": False, "category": "", "message": ""}

    category = normalize_event_category(parsed.get("category"), message)
    if category not in ALLOWED_EVENT_CATEGORIES:
        logging.info("Suppressing out-of-scope vision detection: category=%r message=%r", category, message)
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


def parse_plain_text_detection(text: str) -> Dict[str, Any]:
    """
    Converts non-JSON provider replies into the STASIS alert schema.
    Some OpenAI-compatible providers ignore JSON mode under rate/load pressure.
    """
    message = " ".join(text.strip().split())
    if not message:
        return {"detected": False, "category": "", "message": ""}

    lowered = message.lower()
    negative_phrases = {
        "no person",
        "no people",
        "no human",
        "no humans",
        "not visible",
        "nothing detected",
        "no relevant",
        "does not show",
        "unable to determine",
        "cannot determine",
    }
    if any(phrase in lowered for phrase in negative_phrases):
        return {"detected": False, "category": "", "message": ""}

    category = normalize_event_category("", message)
    if category not in ALLOWED_EVENT_CATEGORIES:
        logging.info("Suppressing non-JSON vision text outside STASIS scope: %r", message[:240])
        return {"detected": False, "category": "", "message": ""}

    normalized = normalize_event_message(category, message)
    if not message_has_project_context(normalized):
        normalized = f"{category} detected: {normalized}"

    return {
        "detected": True,
        "category": category,
        "message": normalized[:500],
        "marker": extract_marker_name(normalized) if category == "marker" else "",
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


def build_vision_messages(image: Any) -> List[Dict[str, Any]]:
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


def frame_to_jpeg_b64(frame: Any, quality: int = 70) -> str:
    import cv2
    quality = max(30, min(95, int(quality)))
    ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError("Could not encode camera frame as JPEG")
    return base64.b64encode(encoded.tobytes()).decode("ascii")


def request_json(url: str, headers: Dict[str, str], payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    import requests
    response = requests.post(url, headers=headers, json=payload, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("Vision provider returned non-object JSON")
    return data


def analyze_with_openai_compatible(name: str, config: Dict[str, Any], frame: Any) -> Dict[str, Any]:
    api_key_env = str(config.get("api_key_env", "")).strip()
    api_key = os.getenv(api_key_env, "") if api_key_env else str(config.get("api_key", ""))
    base_url = str(config.get("base_url", "https://api.openai.com/v1")).rstrip("/")
    model = str(config.get("model", "gpt-4.1-nano"))
    image_b64 = frame_to_jpeg_b64(frame, int(config.get("jpeg_quality", 70)))

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload: Dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are the STASIS rover vision module. Output strict JSON only.",
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": ANALYSIS_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                    },
                ],
            },
        ],
        "temperature": float(config.get("temperature", 0)),
        "max_tokens": int(config.get("max_output_tokens", VISION_CONFIG.get("max_output_tokens", 160))),
    }
    if config.get("json_mode", True):
        payload["response_format"] = {"type": "json_object"}

    data = request_json(f"{base_url}/chat/completions", headers, payload, VISION_REQUEST_TIMEOUT)
    content = data["choices"][0]["message"]["content"]
    logging.info("Vision provider %s returned a response.", name)
    return parse_json_response(extract_model_text(content))


def analyze_with_gemini(config: Dict[str, Any], frame: Any) -> Dict[str, Any]:
    api_key_env = str(config.get("api_key_env", "GEMINI_API_KEY"))
    api_key = os.getenv(api_key_env, "")
    model = str(config.get("model", "gemini-2.5-flash-lite"))
    base_url = str(config.get("base_url", "https://generativelanguage.googleapis.com/v1beta")).rstrip("/")
    image_b64 = frame_to_jpeg_b64(frame, int(config.get("jpeg_quality", 70)))

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": ANALYSIS_PROMPT},
                    {"inline_data": {"mime_type": "image/jpeg", "data": image_b64}},
                ],
            }
        ],
        "generationConfig": {
            "temperature": float(config.get("temperature", 0)),
            "maxOutputTokens": int(config.get("max_output_tokens", VISION_CONFIG.get("max_output_tokens", 160))),
            "responseMimeType": "application/json",
        },
    }
    data = request_json(f"{base_url}/models/{model}:generateContent?key={api_key}", {}, payload, VISION_REQUEST_TIMEOUT)
    parts = data["candidates"][0]["content"]["parts"]
    content = "\n".join(str(part.get("text", "")) for part in parts if isinstance(part, dict))
    return parse_json_response(content)


def analyze_with_anthropic(config: Dict[str, Any], frame: Any) -> Dict[str, Any]:
    api_key_env = str(config.get("api_key_env", "ANTHROPIC_API_KEY"))
    api_key = os.getenv(api_key_env, "")
    base_url = str(config.get("base_url", "https://api.anthropic.com/v1")).rstrip("/")
    model = str(config.get("model", "claude-3-5-haiku-latest"))
    image_b64 = frame_to_jpeg_b64(frame, int(config.get("jpeg_quality", 70)))

    payload = {
        "model": model,
        "max_tokens": int(config.get("max_output_tokens", VISION_CONFIG.get("max_output_tokens", 160))),
        "temperature": float(config.get("temperature", 0)),
        "system": "You are the STASIS rover vision module. Output strict JSON only.",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": ANALYSIS_PROMPT},
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_b64,
                        },
                    },
                ],
            }
        ],
    }
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": str(config.get("anthropic_version", "2023-06-01")),
    }
    data = request_json(f"{base_url}/messages", headers, payload, VISION_REQUEST_TIMEOUT)
    content = extract_model_text(data.get("content", ""))
    return parse_json_response(content)


def analyze_with_ollama(config: Dict[str, Any], frame: Any) -> Dict[str, Any]:
    base_url = str(config.get("base_url", "http://127.0.0.1:11434")).rstrip("/")
    model = str(config.get("model", "llava:7b"))
    image_b64 = frame_to_jpeg_b64(frame, int(config.get("jpeg_quality", 70)))
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {
                "role": "user",
                "content": ANALYSIS_PROMPT,
                "images": [image_b64],
            }
        ],
        "options": {"temperature": float(config.get("temperature", 0))},
    }
    data = request_json(f"{base_url}/api/chat", {"Content-Type": "application/json"}, payload, VISION_REQUEST_TIMEOUT)
    content = data.get("message", {}).get("content", data.get("response", ""))
    return parse_json_response(extract_model_text(content))


def analyze_with_ollama_moondream_pipeline(config: Dict[str, Any], frame: Any) -> Dict[str, Any]:
    """
    Uses a small Ollama vision model as the eyes, then a tiny text model as the JSON formatter.
    """
    base_url = str(config.get("base_url", "http://127.0.0.1:11434")).rstrip("/")
    vision_model = str(config.get("vision_model", "moondream"))
    text_model = str(config.get("text_model", "qwen2.5:0.5b"))
    image_b64 = frame_to_jpeg_b64(frame, int(config.get("jpeg_quality", 60)))
    vision_prompt = str(
        config.get(
            "vision_prompt",
            "Inspect this STASIS rover frame. List whether you see a person/human, animal, "
            "fire/smoke/flame, footprints/tracks/soil disturbance, colored marker/green strip, "
            "and important objects. Be concise.",
        )
    )

    vision_payload = {
        "model": vision_model,
        "stream": False,
        "messages": [
            {
                "role": "user",
                "content": vision_prompt,
                "images": [image_b64],
            }
        ],
        "options": {
            "temperature": float(config.get("vision_temperature", 0)),
            "num_predict": int(config.get("vision_max_tokens", 96)),
        },
    }
    vision_data = request_json(
        f"{base_url}/api/chat",
        {"Content-Type": "application/json"},
        vision_payload,
        float(config.get("vision_timeout_seconds", VISION_REQUEST_TIMEOUT)),
    )
    vision_text = extract_model_text(vision_data.get("message", {}).get("content", vision_data.get("response", "")))

    if not config.get("use_text_formatter", True):
        return parse_json_response(vision_text)

    formatter_prompt = str(
        config.get(
            "formatter_prompt",
            "Convert the vision notes into exactly one STASIS JSON object and no Markdown. "
            "Allowed categories: human, animal, track, fire, marker. "
            "Return detected true only for those STASIS events. Intruders are human. "
            "Colored green strips are marker. If no event is visible, return "
            "{\"detected\": false, \"category\": \"\", \"message\": \"\"}. "
            "Keep message short and specific.",
        )
    )
    formatter_payload = {
        "model": text_model,
        "stream": False,
        "messages": [
            {
                "role": "user",
                "content": f"{formatter_prompt}\n\nVision notes:\n{vision_text}",
            }
        ],
        "options": {
            "temperature": float(config.get("formatter_temperature", 0)),
            "num_predict": int(config.get("formatter_max_tokens", VISION_CONFIG.get("max_output_tokens", 160))),
        },
    }
    formatter_data = request_json(
        f"{base_url}/api/chat",
        {"Content-Type": "application/json"},
        formatter_payload,
        float(config.get("formatter_timeout_seconds", VISION_REQUEST_TIMEOUT)),
    )
    content = formatter_data.get("message", {}).get("content", formatter_data.get("response", ""))
    return parse_json_response(extract_model_text(content))


def analyze_with_local_gemma(frame: Any) -> Dict[str, Any]:
    """
    Invokes the pipeline to process a raw frame.
    """
    if vision_pipe is None:
        raise RuntimeError("Local Gemma provider is enabled, but the pipeline is not loaded")

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


def analyze_frame(frame: Any) -> Dict[str, Any]:
    """
    Tries configured vision providers in order until one succeeds.
    """
    if not VISION_CONFIG.get("enabled", VISION_ENABLED):
        return {"detected": False, "message": ""}

    for provider_name in VISION_PROVIDER_ORDER:
        config = get_provider_config(provider_name)
        if not provider_enabled(provider_name, config):
            continue

        provider_type = str(config.get("type", provider_name)).strip().lower()
        try:
            if provider_type == "local_gemma":
                result = analyze_with_local_gemma(frame)
            elif provider_type in {"openai", "openai_compatible", "lmstudio", "qwen", "kimi", "zhipu"}:
                result = analyze_with_openai_compatible(provider_name, config, frame)
            elif provider_type == "gemini":
                result = analyze_with_gemini(config, frame)
            elif provider_type == "anthropic":
                result = analyze_with_anthropic(config, frame)
            elif provider_type == "ollama":
                result = analyze_with_ollama(config, frame)
            elif provider_type in {"ollama_moondream_pipeline", "moondream_pipeline"}:
                result = analyze_with_ollama_moondream_pipeline(config, frame)
            else:
                logging.warning("Unknown vision provider type %r for %s", provider_type, provider_name)
                continue

            logging.info("Vision provider %s succeeded.", provider_name)
            return result
        except Exception as exc:
            logging.warning("Vision provider %s failed: %s", provider_name, exc)

    return {"detected": False, "category": "", "message": ""}


def save_alert_frame(frame: Any) -> str:
    """
    Persists alert snapshots to disk under the alerts subdirectory.
    """
    import cv2
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
        jpeg_bytes = latest_frame_jpeg
        if jpeg_bytes is None:
            time.sleep(0.05)
            continue

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + jpeg_bytes
            + b"\r\n"
        )
        time.sleep(1.0 / max(1, CAMERA_FPS))


def handle_camera_frame(payload: Dict[str, Any]) -> None:
    """
    Receives JPEG frames from the Raspberry Pi webcam over the rover WebSocket.
    """
    global latest_frame, latest_frame_jpeg, latest_frame_metadata

    if payload.get("format") != "jpeg":
        logging.warning("Ignoring unsupported rover camera frame format: %r", payload.get("format"))
        return

    try:
        raw = base64.b64decode(str(payload["image_b64"]))
        if DETECTOR_BACKEND != "none":
            import cv2
            import numpy as np
            image_array = np.frombuffer(raw, dtype=np.uint8)
            frame = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            if frame is None:
                logging.warning("Decoded rover camera frame was empty.")
                return
            latest_frame = frame
        latest_frame_jpeg = raw
    except Exception as exc:
        logging.warning("Could not decode rover camera frame: %s", exc)
        return

    latest_frame_metadata = {
        "source": "rover",
        "width": payload.get("width"),
        "height": payload.get("height"),
        "captured_at": payload.get("captured_at"),
        "received_at": time.time(),
    }
    socketio.emit("camera_status", {"source": "rover", "connected": True})
    append_event_log("camera_frame_received", {
        "format": payload.get("format"),
        "byte_length": len(str(payload.get("image_b64", ""))),
        "width": payload.get("width"),
        "height": payload.get("height")
    })


def send_rover_command(command: Dict[str, Any]) -> bool:
    """
    Transmits a command structure to the connected physical rover via WebSocket or Socket.IO.
    
    @return True if transmitted successfully, otherwise False.
    """
    global rover_ws

    summary = {
        "cmd": command.get("cmd", command.get("type")),
        "target": command.get("target", command.get("direction"))
    }

    if rover_ws is not None:
        try:
            rover_ws.send(json.dumps(command))
            logging.info("Dispatched websocket command to rover: %s", command)
            append_event_log("command_sent", summary)
            return True
        except ConnectionClosed:
            rover_ws = None
            append_event_log("command_failed", {"reason": "ConnectionClosed", **summary})

    if rover_socketio_sid is not None:
        try:
            socketio.emit("rover_command", command, to=rover_socketio_sid)
            logging.info("Dispatched SocketIO command to rover: %s", command)
            append_event_log("command_sent", summary)
            return True
        except Exception as exc:
            logging.error("Failed sending SocketIO command: %s", exc)
            append_event_log("command_failed", {"reason": str(exc), **summary})

    logging.warning("Command drop: No rover client connection registered. Command: %s", command)
    append_event_log("command_failed", {"reason": "no_connection", **summary})
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
            if not VISION_CONFIG.get("enabled", VISION_ENABLED):
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
                "x": rover_pose["x"],
                "y": rover_pose["y"],
                "heading": rover_pose["heading"],
            }
            if analysis.get("marker"):
                payload["marker"] = analysis["marker"]

            logging.info("Vision result ready for rover decision: Category=%s Message=%s", analysis["category"], analysis["message"])
            sent = send_rover_command({"type": "vision_result", "detected": True, **payload})
            if not sent:
                logging.warning("Vision result could not be sent to rover for decision.")
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


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def estimate_detection_target(
    detection: Dict[str, Any],
    frame_width: float,
    frame_height: float,
) -> Dict[str, Any]:
    """
    Projects a camera detection onto the simple local dashboard map.

    This is not SLAM. It is a stable demo estimate so dashboard tracking does
    not place every object directly underneath the rover marker.
    """
    box = detection.get("box") if isinstance(detection.get("box"), dict) else {}
    box_width = float(box.get("width", 0) or 0)
    box_height = float(box.get("height", 0) or 0)
    box_x = float(box.get("x", frame_width / 2.0 - box_width / 2.0) or 0)
    center_x = box_x + box_width / 2.0
    horizontal = clamp((center_x - frame_width / 2.0) / max(1.0, frame_width / 2.0), -1.0, 1.0)
    area_ratio = clamp((box_width * box_height) / max(1.0, frame_width * frame_height), 0.0, 1.0)

    forward_cm = clamp(320.0 - area_ratio * 900.0, 45.0, 320.0)
    side_cm = horizontal * 190.0
    yaw_rad = math.radians(float(rover_pose.get("yaw", 0.0) or 0.0))
    forward_px = forward_cm / PIXEL_TO_CM
    side_px = side_cm / PIXEL_TO_CM
    target_x = clamp(
        rover_pose["x"] + math.cos(yaw_rad) * forward_px + math.cos(yaw_rad + math.pi / 2.0) * side_px,
        0.0,
        800.0,
    )
    target_y = clamp(
        rover_pose["y"] + math.sin(yaw_rad) * forward_px + math.sin(yaw_rad + math.pi / 2.0) * side_px,
        0.0,
        800.0,
    )

    if abs(side_cm) < 18.0:
        direction = f"forward {round(forward_cm)} cm"
        side = "center"
    elif side_cm < 0:
        direction = f"forward {round(forward_cm)} cm, left {round(abs(side_cm))} cm"
        side = "left"
    else:
        direction = f"forward {round(forward_cm)} cm, right {round(abs(side_cm))} cm"
        side = "right"

    return {
        "x": target_x,
        "y": target_y,
        "guidance": {
            "direction": direction,
            "forward_cm": round(forward_cm),
            "side": side,
            "side_cm": round(abs(side_cm)),
            "image_x": round(center_x, 1),
            "image_y": round(float(box.get("y", 0) or 0) + box_height / 2.0, 1),
            "image_vertical_ratio": round((float(box.get("y", 0) or 0) + box_height / 2.0) / max(1.0, frame_height), 3),
        },
    }


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

    mode = str(payload.get("mode") or "")
    if mode:
        rover_pose["mode"] = mode
    update_distance_from_home()
    socketio.emit("rover_position", rover_pose.copy())
    append_event_log("telemetry_update", {
        "heading": rover_pose.get("heading"),
        "distance_traveled": distance_traveled,
        "mode": mode
    })


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
    append_event_log("scan_received", {"point_count": len(latest_scan)})


def handle_vision_decision(payload: Dict[str, Any]) -> None:
    """
    Applies the Raspberry Pi's decision after Windows returns a vision result.
    """
    if not payload.get("detected") or not payload.get("alert", True):
        return

    category = str(payload.get("category") or "event").lower()
    image_path = str(payload.get("image_path") or "")
    alert_payload = {
        "id": f"alert_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
        "category": category,
        "message": str(payload.get("message") or "Activity detected."),
        "image_path": image_path,
        "action": payload.get("action", "alert"),
        "x": float(payload.get("x", rover_pose["x"])),
        "y": float(payload.get("y", rover_pose["y"])),
        "heading": float(payload.get("heading", rover_pose["heading"])),
        "label": str(payload.get("label") or ""),
        "box": payload.get("box", {}),
        "frame_width": payload.get("frame_width", 0),
        "frame_height": payload.get("frame_height", 0),
        "guidance": payload.get("guidance", {}),
        "mode": payload.get("mode", ""),
    }

    marker = str(payload.get("marker") or "")
    if marker:
        alert_payload["marker"] = marker
        remember_marker(marker, image_path)

    logging.info("Rover approved alert: category=%s action=%s", category, alert_payload["action"])
    socketio.emit("new_alert", alert_payload)
    socketio.emit(
        "rover_status",
        {
            "status": "vision_decision",
            "message": f"{category}: {alert_payload['action']}",
        },
    )


def _object_detection_message(detection: Dict[str, Any]) -> str:
    label = str(detection.get("label") or detection.get("category_hint") or "target").replace("_", " ")
    category = str(detection.get("category_hint") or "object").lower()
    confidence = detection.get("confidence", 0)
    try:
        confidence_value = float(confidence)
        confidence_percent = confidence_value if confidence_value > 1.0 else confidence_value * 100.0
        suffix = f" at {confidence_percent:.0f}%"
    except (TypeError, ValueError):
        suffix = ""
    if category == "human":
        return f"Human detected: {label}{suffix}."
    if category == "marker":
        return f"Green strip marker detected{suffix}."
    if category == "animal":
        return f"Animal detected: {label}{suffix}."
    return f"Object detected: {label}{suffix}."


def handle_object_detection_report(payload: Dict[str, Any]) -> None:
    """
    Converts Pi-side detector output into a rover vision_result command.

    This keeps Gemma/VLM disabled for the demo: the Pi runs detection, the server
    only turns structured detection output into the command format already used by
    rover_client.py.
    """
    detections = payload.get("detections", [])
    if not isinstance(detections, list) or not detections:
        return

    priority = {"human": 0, "marker": 1, "animal": 2, "object": 3}
    ignored_demo_labels = {
        label.strip().lower()
        for label in os.getenv("STASIS_PI_IGNORE_LABELS", "").split(",")
        if label.strip()
    }
    min_custom_confidence = float(os.getenv("STASIS_PI_MIN_OBJECT_CONFIDENCE", "0.55"))
    min_animal_confidence = float(os.getenv("STASIS_PI_MIN_ANIMAL_CONFIDENCE", "0.68"))
    min_common_object_confidence = float(os.getenv("STASIS_PI_MIN_COMMON_OBJECT_CONFIDENCE", "0.55"))
    max_box_area_ratio = float(os.getenv("STASIS_PI_MAX_BOX_AREA_RATIO", "0.70"))
    max_box_width_ratio = float(os.getenv("STASIS_PI_MAX_BOX_WIDTH_RATIO", "0.96"))
    max_box_height_ratio = float(os.getenv("STASIS_PI_MAX_BOX_HEIGHT_RATIO", "0.96"))
    frame_width = float(payload.get("frame_width") or payload.get("width") or 640)
    frame_height = float(payload.get("frame_height") or payload.get("height") or 480)
    valid: List[Dict[str, Any]] = []
    for item in detections:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category_hint") or "").strip().lower()
        if category not in {"human", "animal", "object", "marker"}:
            continue
        label = str(item.get("label") or "").strip().lower()
        confidence = float(item.get("confidence", 0) or 0)
        detector = str(item.get("detector") or "").strip().lower()
        box = item.get("box") if isinstance(item.get("box"), dict) else {}
        box_width = float(box.get("width", 0) or 0)
        box_height = float(box.get("height", 0) or 0)
        box_area_ratio = (box_width * box_height) / max(1.0, frame_width * frame_height)
        box_width_ratio = box_width / max(1.0, frame_width)
        box_height_ratio = box_height / max(1.0, frame_height)
        if label in ignored_demo_labels:
            logging.info("Filtered ignored Pi detection label=%s confidence=%.2f.", label, confidence)
            record_detection_event(item, False, "ignored_label")
            continue
        if category == "object" and (
            box_area_ratio > max_box_area_ratio
            or box_width_ratio > max_box_width_ratio
            or box_height_ratio > max_box_height_ratio
        ):
            logging.info(
                "Filtered oversized Pi object label=%s confidence=%.2f box_area=%.2f width=%.2f height=%.2f.",
                label,
                confidence,
                box_area_ratio,
                box_width_ratio,
                box_height_ratio,
            )
            record_detection_event(item, False, "oversized_box")
            continue
        if category == "object" and detector != "coco" and confidence < min_custom_confidence:
            logging.info("Filtered weak Pi custom object label=%s confidence=%.2f.", label, confidence)
            record_detection_event(item, False, "weak_custom")
            continue
        if category == "object" and detector == "coco" and confidence < min_common_object_confidence:
            logging.info("Filtered weak Pi common object label=%s confidence=%.2f.", label, confidence)
            record_detection_event(item, False, "weak_common")
            continue
        if category == "animal" and confidence < min_animal_confidence:
            logging.info("Filtered weak Pi animal label=%s confidence=%.2f.", label, confidence)
            record_detection_event(item, False, "weak_animal")
            continue
        record_detection_event(item, True, "accepted")
        valid.append(item)
    if not valid:
        return

    valid.sort(key=lambda item: (priority.get(str(item.get("category_hint", "")).lower(), 9), -float(item.get("confidence", 0) or 0)))
    image_path = ""
    if payload.get("image_b64"):
        try:
            import cv2
            import numpy as np
            image_bytes = base64.b64decode(str(payload["image_b64"]))
            image_path = save_alert_frame(cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR))
        except Exception as exc:
            logging.warning("Could not save object detection snapshot: %s", exc)

    emitted_categories: set[str] = set()
    for detection in valid:
        category = str(detection.get("category_hint") or "object").lower()
        if category in emitted_categories:
            continue
        emitted_categories.add(category)

        marker = str(detection.get("marker") or "")
        if category == "marker" and not marker:
            marker = "green_strip"

        command = {
            "type": "vision_result",
            "detected": True,
            "category": category,
            "message": _object_detection_message(detection),
            "image_path": image_path,
            "x": rover_pose["x"],
            "y": rover_pose["y"],
            "heading": rover_pose["heading"],
            "label": detection.get("label", ""),
            "box": detection.get("box", {}),
            "frame_width": int(frame_width),
            "frame_height": int(frame_height),
        }
        if marker:
            command["marker"] = marker
        target = estimate_detection_target(detection, frame_width, frame_height)
        command["x"] = target["x"]
        command["y"] = target["y"]
        command["guidance"] = target["guidance"]

        logging.info("Pi object detection converted to rover vision_result: %s", command["message"])
        sent = send_rover_command(command)
        if not sent:
            logging.warning("Object detection result could not be sent to rover for decision.")
        if len(emitted_categories) >= 4:
            break


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

    if payload.get("type") == "camera_frame":
        handle_camera_frame(payload)
        return

    if payload.get("type") == "vision_decision":
        handle_vision_decision(payload)
        return

    if payload.get("type") == "object_detection":
        handle_object_detection_report(payload)
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
    append_event_log("rover_connected", {"client_id": client_id})

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
        append_event_log("rover_disconnected", {"client_id": client_id})
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
    emit("detection_debug", {"detections": recent_detections})


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
    marker = "green_strip"
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

    marker = "green_strip"
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


@socketio.on("human_decision")
def on_human_decision(payload: Optional[Dict[str, Any]] = None) -> None:
    """
    Routes dashboard human-detection decisions to the rover mode controller.
    """
    action = ""
    if isinstance(payload, dict):
        action = str(payload.get("action") or "").strip().lower()
    command_by_action = {
        "follow": {"cmd": "follow"},
        "stay_stopped": {"cmd": "stay_stopped"},
        "resume_patrol": {"cmd": "resume_patrol"},
    }
    command = command_by_action.get(action)
    if command is None:
        emit("human_decision_error", {"message": "Unknown human decision action."})
        return
    sent = send_rover_command(command)
    emit("human_decision_sent", {"sent": sent, "action": action})


@socketio.on("track_target")
def on_track_target(payload: Optional[Dict[str, Any]] = None) -> None:
    """
    Stores the dashboard-selected tracking target so UI state is explicit.

    Motor follow is still controlled by the separate Follow button. This keeps
    clicking a map/alert target from unexpectedly moving the rover.
    """
    global tracked_target

    if not isinstance(payload, dict):
        emit("track_target_error", {"message": "Track target payload must be an object."})
        return
    tracked_target = {
        "id": str(payload.get("id") or ""),
        "category": str(payload.get("category") or "event"),
        "label": str(payload.get("label") or ""),
        "x": payload.get("x"),
        "y": payload.get("y"),
        "guidance": payload.get("guidance", {}),
        "selected_at": datetime.now().isoformat(timespec="seconds"),
    }
    emit("track_target_selected", tracked_target)


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
    
    # Load neural models if enabled
    if VISION_ENABLED and DETECTOR_BACKEND != "none":
        load_vision_model()
        
        # Start camera and vision processing. Default camera source is the Raspberry Pi rover.
        if CAMERA_SOURCE == "local":
            socketio.start_background_task(webcam_capture_loop)
        else:
            logging.info("Waiting for Raspberry Pi webcam frames over the rover WebSocket.")
        socketio.start_background_task(vision_analysis_loop)
    else:
        logging.info("Vision backend disabled; not starting capture/analysis loops.")
    
    # Execute Flask SocketIO webserver
    logging.info("Starting STASIS Flask-SocketIO central webserver on 0.0.0.0:5000...")
    append_event_log("server_start", {"message": "Server started"})
    socketio.run(app, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    main()

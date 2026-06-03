"""
STASIS Windows-side object-detection server.

Run this on the Windows laptop while the Raspberry Pi streams webcam frames and
controls the motors. The laptop runs YOLO from an ONNX model, emits dashboard
alerts immediately, and still sends the normal vision_result command to the Pi
so human/fire events can stop the rover.
"""

from __future__ import annotations

import base64
import json
import logging
import math
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable

import cv2
import numpy as np
import requests

import security_rover_server_windows as base

base.ALLOWED_EVENT_CATEGORIES.add("object")

SERVER_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL_PATH = SERVER_DIR / "models" / "yolo11n.onnx"
DEFAULT_CUSTOM_MODEL_PATH = SERVER_DIR / "models" / "stasis_custom.onnx"
DEFAULT_CUSTOM_LABELS_PATH = SERVER_DIR / "models" / "stasis_custom.labels.txt"

COCO_LABELS = [
    "person",
    "bicycle",
    "car",
    "motorcycle",
    "airplane",
    "bus",
    "train",
    "truck",
    "boat",
    "traffic light",
    "fire hydrant",
    "stop sign",
    "parking meter",
    "bench",
    "bird",
    "cat",
    "dog",
    "horse",
    "sheep",
    "cow",
    "elephant",
    "bear",
    "zebra",
    "giraffe",
    "backpack",
    "umbrella",
    "handbag",
    "tie",
    "suitcase",
    "frisbee",
    "skis",
    "snowboard",
    "sports ball",
    "kite",
    "baseball bat",
    "baseball glove",
    "skateboard",
    "surfboard",
    "tennis racket",
    "bottle",
    "wine glass",
    "cup",
    "fork",
    "knife",
    "spoon",
    "bowl",
    "banana",
    "apple",
    "sandwich",
    "orange",
    "broccoli",
    "carrot",
    "hot dog",
    "pizza",
    "donut",
    "cake",
    "chair",
    "couch",
    "potted plant",
    "bed",
    "dining table",
    "toilet",
    "tv",
    "laptop",
    "mouse",
    "remote",
    "keyboard",
    "cell phone",
    "microwave",
    "oven",
    "toaster",
    "sink",
    "refrigerator",
    "book",
    "clock",
    "vase",
    "scissors",
    "teddy bear",
    "hair drier",
    "toothbrush",
]

ANIMAL_LABELS = {
    "bird",
    "cat",
    "dog",
    "horse",
    "sheep",
    "cow",
    "elephant",
    "bear",
    "zebra",
    "giraffe",
}
COMMON_ALLOWED_LABELS = {"person", "cell phone", *ANIMAL_LABELS}
IGNORED_LABELS = {
    "street",
    "road",
    "sidewalk",
    "floor",
    "wall",
    "ceiling",
    "door",
    "window",
    "room",
    "building",
    "house",
    "sky",
    "tree",
    "plant",
    "parking meter",
}

OBJECT_REVIEW_PROVIDER = os.getenv("STASIS_OBJECT_REVIEW_PROVIDER", "fallback").strip().lower()
OBJECT_REVIEW_TIMEOUT = float(os.getenv("STASIS_OBJECT_REVIEW_TIMEOUT", "20"))
OBJECT_REVIEW_COOLDOWN = float(os.getenv("STASIS_OBJECT_REVIEW_COOLDOWN", "8"))
OBJECT_ANALYSIS_INTERVAL = float(os.getenv("STASIS_OBJECT_ANALYSIS_INTERVAL_SECONDS", "0.8"))
ONNX_MODEL_PATH = Path(os.getenv("STASIS_YOLO_ONNX_MODEL", str(DEFAULT_MODEL_PATH)))
CUSTOM_ONNX_MODEL_PATH = Path(os.getenv("STASIS_CUSTOM_YOLO_ONNX_MODEL", str(DEFAULT_CUSTOM_MODEL_PATH)))
CUSTOM_LABELS_PATH = Path(os.getenv("STASIS_CUSTOM_YOLO_LABELS", str(DEFAULT_CUSTOM_LABELS_PATH)))
ONNX_INPUT_SIZE = int(os.getenv("STASIS_YOLO_INPUT_SIZE", "640"))
CUSTOM_ONNX_INPUT_SIZE = int(os.getenv("STASIS_CUSTOM_YOLO_INPUT_SIZE", str(ONNX_INPUT_SIZE)))
ONNX_CONFIDENCE = float(os.getenv("STASIS_YOLO_CONFIDENCE", "0.35"))
CUSTOM_ONNX_CONFIDENCE = float(os.getenv("STASIS_CUSTOM_YOLO_CONFIDENCE", "0.45"))
ONNX_NMS_THRESHOLD = float(os.getenv("STASIS_YOLO_NMS_THRESHOLD", "0.45"))
ONNX_MAX_DETECTIONS = int(os.getenv("STASIS_YOLO_MAX_DETECTIONS", "12"))
DRAW_OVERLAY = os.getenv("STASIS_YOLO_DRAW_OVERLAY", "true").strip().lower() not in {"0", "false", "no", "off"}
DETECTION_AUTHORITY = os.getenv("STASIS_DETECTION_AUTHORITY", "windows").strip().lower()
GREEN_STRIP_MIN_CONFIDENCE = float(os.getenv("STASIS_GREEN_STRIP_MIN_CONFIDENCE", "0.70"))
GREEN_STRIP_MIN_CENTER_Y_RATIO = float(os.getenv("STASIS_GREEN_STRIP_MIN_CENTER_Y_RATIO", "0.45"))
CUSTOM_MAX_BOX_AREA_RATIO = float(os.getenv("STASIS_CUSTOM_MAX_BOX_AREA_RATIO", "0.62"))
CUSTOM_EDGE_TOUCH_LIMIT = int(os.getenv("STASIS_CUSTOM_EDGE_TOUCH_LIMIT", "2"))
CUSTOM_MIN_OBJECT_CONFIDENCE = float(os.getenv("STASIS_CUSTOM_MIN_OBJECT_CONFIDENCE", "0.68"))
CUSTOM_MAX_BOX_WIDTH_RATIO = float(os.getenv("STASIS_CUSTOM_MAX_BOX_WIDTH_RATIO", "0.58"))
CUSTOM_MAX_BOX_HEIGHT_RATIO = float(os.getenv("STASIS_CUSTOM_MAX_BOX_HEIGHT_RATIO", "0.58"))
COCO_MIN_ANIMAL_CONFIDENCE = float(os.getenv("STASIS_COCO_MIN_ANIMAL_CONFIDENCE", "0.68"))
COCO_MIN_OBJECT_CONFIDENCE = float(os.getenv("STASIS_COCO_MIN_OBJECT_CONFIDENCE", "0.70"))
OLLAMA_BASE_URL = os.getenv("STASIS_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_TEXT_MODEL = os.getenv("STASIS_OLLAMA_TEXT_MODEL", "qwen2.5:0.5b")
LMSTUDIO_BASE_URL = os.getenv("STASIS_LMSTUDIO_URL", "http://127.0.0.1:1234/v1").rstrip("/")
LMSTUDIO_TEXT_MODEL = os.getenv("STASIS_LMSTUDIO_TEXT_MODEL", "qwen2.5-0.5b-instruct")

last_object_signature = ""
last_object_review_at = 0.0
detectors: list["YoloOnnxDetector"] = []
original_handle_rover_report = base.handle_rover_report


def label_key(label: str) -> str:
    return str(label).strip().lower().replace("_", " ")


def category_for_label(label: str) -> str:
    label = label.strip().lower()
    label = label.replace("_", " ")
    if label == "person":
        return "human"
    if label == "green strip":
        return "marker"
    if label in ANIMAL_LABELS:
        return "animal"
    if label in IGNORED_LABELS:
        return ""
    return "object"


def confidence_score(item: Dict[str, Any]) -> float:
    value = float(item.get("confidence", 0) or 0)
    return value / 100.0 if value > 1.0 else value


def confidence_percent_text(value: Any) -> str:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return str(value)
    if confidence <= 1.0:
        confidence *= 100.0
    return f"{confidence:.0f}%"


def letterbox(frame: np.ndarray, size: int) -> tuple[np.ndarray, float, float, float]:
    height, width = frame.shape[:2]
    scale = min(size / width, size / height)
    resized_width = int(round(width * scale))
    resized_height = int(round(height * scale))
    resized = cv2.resize(frame, (resized_width, resized_height), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    pad_x = (size - resized_width) / 2.0
    pad_y = (size - resized_height) / 2.0
    canvas[int(pad_y) : int(pad_y) + resized_height, int(pad_x) : int(pad_x) + resized_width] = resized
    return canvas, scale, pad_x, pad_y


class YoloOnnxDetector:
    def __init__(
        self,
        model_path: Path,
        input_size: int,
        labels: list[str],
        name: str,
        allowed_labels: set[str] | None = None,
        confidence: float | None = None,
    ) -> None:
        self.model_path = model_path
        self.input_size = input_size
        self.labels = labels
        self.name = name
        self.allowed_labels = {label_key(label) for label in allowed_labels} if allowed_labels else set()
        self.confidence = ONNX_CONFIDENCE if confidence is None else confidence
        self.session: Any = None
        self.input_name = ""
        self.output_names: list[str] = []

    def setup(self) -> bool:
        if not self.model_path.exists():
            logging.warning("Windows YOLO ONNX model missing: %s", self.model_path)
            return False
        try:
            import onnxruntime as ort
        except ImportError:
            logging.error("onnxruntime is required on Windows. Install with: python -m pip install onnxruntime")
            return False
        providers = ["CPUExecutionProvider"]
        self.session = ort.InferenceSession(str(self.model_path), providers=providers)
        self.input_name = self.session.get_inputs()[0].name
        self.output_names = [output.name for output in self.session.get_outputs()]
        logging.info("Windows YOLO ONNX detector %s loaded from %s with %d labels.", self.name, self.model_path, len(self.labels))
        return True

    def detect(self, frame: np.ndarray) -> list[dict[str, Any]]:
        if self.session is None:
            return []
        image, scale, pad_x, pad_y = letterbox(frame, self.input_size)
        blob = cv2.cvtColor(image, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        blob = np.transpose(blob, (2, 0, 1))[None, ...]
        outputs = self.session.run(self.output_names, {self.input_name: blob})
        return self.decode_outputs(outputs, frame.shape[1], frame.shape[0], scale, pad_x, pad_y)

    def decode_outputs(
        self,
        outputs: Iterable[np.ndarray],
        frame_width: int,
        frame_height: int,
        scale: float,
        pad_x: float,
        pad_y: float,
    ) -> list[dict[str, Any]]:
        raw = list(outputs)[0]
        predictions = np.squeeze(raw)
        if predictions.ndim != 2:
            logging.warning("Unexpected YOLO ONNX output shape: %s", raw.shape)
            return []
        if predictions.shape[0] < predictions.shape[1]:
            predictions = predictions.T

        boxes: list[list[int]] = []
        scores: list[float] = []
        class_ids: list[int] = []
        for row in predictions:
            if row.shape[0] < 6:
                continue
            class_scores = row[4:]
            objectness = 1.0
            if row.shape[0] == 85:
                objectness = float(row[4])
                class_scores = row[5:]
            class_id = int(np.argmax(class_scores))
            confidence = float(class_scores[class_id]) * objectness
            if confidence < self.confidence or class_id >= len(self.labels):
                continue

            cx, cy, width, height = [float(value) for value in row[:4]]
            x1 = int(round((cx - width / 2.0 - pad_x) / scale))
            y1 = int(round((cy - height / 2.0 - pad_y) / scale))
            x2 = int(round((cx + width / 2.0 - pad_x) / scale))
            y2 = int(round((cy + height / 2.0 - pad_y) / scale))
            x1 = max(0, min(frame_width - 1, x1))
            y1 = max(0, min(frame_height - 1, y1))
            x2 = max(0, min(frame_width - 1, x2))
            y2 = max(0, min(frame_height - 1, y2))
            if x2 <= x1 or y2 <= y1:
                continue
            label = label_key(self.labels[class_id])
            if self.allowed_labels and label not in self.allowed_labels:
                continue
            category = category_for_label(label)
            if not category:
                continue
            boxes.append([x1, y1, x2 - x1, y2 - y1])
            scores.append(confidence)
            class_ids.append(class_id)

        indices = cv2.dnn.NMSBoxes(boxes, scores, self.confidence, ONNX_NMS_THRESHOLD)
        if len(indices) == 0:
            return []

        detections: list[dict[str, Any]] = []
        for index in np.array(indices).flatten()[:ONNX_MAX_DETECTIONS]:
            label = label_key(self.labels[class_ids[int(index)]])
            detections.append(
                {
                    "label": label,
                    "category_hint": category_for_label(label),
                    "confidence": round(float(scores[int(index)]), 3),
                    "box": {
                        "x": int(boxes[int(index)][0]),
                        "y": int(boxes[int(index)][1]),
                        "width": int(boxes[int(index)][2]),
                        "height": int(boxes[int(index)][3]),
                    },
                    "detector": self.name,
                }
            )
        detections.sort(key=confidence_score, reverse=True)
        return detections


def load_labels(path: Path) -> list[str]:
    if not path.exists():
        logging.warning("Custom YOLO labels file missing: %s", path)
        return []
    labels = [label_key(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return labels


def draw_detections(frame: np.ndarray, detections: list[dict[str, Any]]) -> np.ndarray:
    overlay = frame.copy()
    for item in detections:
        box = item.get("box", {})
        x = int(box.get("x", 0))
        y = int(box.get("y", 0))
        width = int(box.get("width", 0))
        height = int(box.get("height", 0))
        if width <= 0 or height <= 0:
            continue
        category = str(item.get("category_hint", "object"))
        color = (0, 255, 0)
        if category == "human":
            color = (0, 220, 255)
        elif category == "animal":
            color = (120, 255, 120)
        cv2.rectangle(overlay, (x, y), (x + width, y + height), color, 2)
        cv2.putText(
            overlay,
            f"{item.get('label', 'object')} {confidence_percent_text(item.get('confidence', 0))}",
            (x, max(18, y - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2,
        )
    return overlay


def filter_scene_detections(
    detections: list[dict[str, Any]],
    frame_width: int,
    frame_height: int,
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for item in detections:
        label = label_key(str(item.get("label", "")))
        confidence = confidence_score(item)
        box = item.get("box", {})
        detector = str(item.get("detector", ""))
        category = str(item.get("category_hint", ""))
        x = float(box.get("x", 0))
        y = float(box.get("y", 0))
        width = float(box.get("width", 0))
        height = float(box.get("height", 0))
        center_y_ratio = (y + height / 2.0) / max(1.0, float(frame_height))

        if detector == "stasis_custom" and category in {"object", "marker"}:
            area_ratio = (width * height) / max(1.0, float(frame_width * frame_height))
            width_ratio = width / max(1.0, float(frame_width))
            height_ratio = height / max(1.0, float(frame_height))
            edge_touches = sum(
                (
                    x <= 4,
                    y <= 4,
                    x + width >= frame_width - 4,
                    y + height >= frame_height - 4,
                )
            )
            if category == "object" and confidence < CUSTOM_MIN_OBJECT_CONFIDENCE:
                logging.info(
                    "Filtered weak custom %s detection at %s confidence.",
                    label,
                    confidence_percent_text(confidence),
                )
                continue
            if area_ratio > CUSTOM_MAX_BOX_AREA_RATIO:
                logging.info(
                    "Filtered oversized %s detection: area_ratio=%.2f confidence=%s.",
                    label,
                    area_ratio,
                    confidence_percent_text(confidence),
                )
                continue
            if width_ratio > CUSTOM_MAX_BOX_WIDTH_RATIO or height_ratio > CUSTOM_MAX_BOX_HEIGHT_RATIO:
                logging.info(
                    "Filtered broad %s detection: width_ratio=%.2f height_ratio=%.2f confidence=%s.",
                    label,
                    width_ratio,
                    height_ratio,
                    confidence_percent_text(confidence),
                )
                continue
            if edge_touches >= CUSTOM_EDGE_TOUCH_LIMIT:
                logging.info(
                    "Filtered edge-hugging %s detection: edge_touches=%d confidence=%s.",
                    label,
                    edge_touches,
                    confidence_percent_text(confidence),
                )
                continue

        if detector == "coco" and category == "animal" and confidence < COCO_MIN_ANIMAL_CONFIDENCE:
            logging.info(
                "Filtered weak COCO animal %s detection at %s confidence.",
                label,
                confidence_percent_text(confidence),
            )
            continue

        if detector == "coco" and category == "object" and confidence < COCO_MIN_OBJECT_CONFIDENCE:
            logging.info(
                "Filtered weak COCO object %s detection at %s confidence.",
                label,
                confidence_percent_text(confidence),
            )
            continue

        if label == "green strip":
            if confidence < GREEN_STRIP_MIN_CONFIDENCE:
                logging.info(
                    "Filtered weak green strip detection at %s confidence.",
                    confidence_percent_text(confidence),
                )
                continue
            if center_y_ratio < GREEN_STRIP_MIN_CENTER_Y_RATIO:
                logging.info(
                    "Filtered green strip above floor zone: center_y_ratio=%.2f.",
                    center_y_ratio,
                )
                continue

        filtered.append(item)
    return filtered


def estimate_detection_guidance(best: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    box = best.get("box", {}) if isinstance(best.get("box"), dict) else {}
    width = float(payload.get("width") or 640)
    height = float(payload.get("height") or 480)
    box_x = float(box.get("x", width / 2))
    box_y = float(box.get("y", height / 2))
    box_w = max(1.0, float(box.get("width", 1)))
    box_h = max(1.0, float(box.get("height", 1)))
    center_x = box_x + box_w / 2.0
    center_y = box_y + box_h / 2.0

    horizontal_ratio = (center_x - width / 2.0) / max(1.0, width / 2.0)
    vertical_ratio = 1.0 - (center_y / max(1.0, height))
    object_ratio = box_h / max(1.0, height)
    estimated_forward_cm = int(max(30, min(500, 170 / max(0.08, object_ratio))))
    estimated_side_cm = int(max(0, min(300, abs(horizontal_ratio) * estimated_forward_cm * 0.75)))
    side = "right" if horizontal_ratio > 0.18 else "left" if horizontal_ratio < -0.18 else "center"
    if estimated_forward_cm <= 60:
        direction = "nearby"
    elif side == "center":
        direction = f"forward {estimated_forward_cm} cm"
    else:
        direction = f"forward {estimated_forward_cm} cm, {side} {estimated_side_cm} cm"
    return {
        "direction": direction,
        "forward_cm": estimated_forward_cm,
        "side": side,
        "side_cm": estimated_side_cm,
        "image_x": round(center_x, 1),
        "image_y": round(center_y, 1),
        "image_vertical_ratio": round(vertical_ratio, 3),
    }


def estimate_map_position(guidance: Dict[str, Any]) -> Dict[str, float]:
    forward_cm = float(guidance.get("forward_cm", 0) or 0)
    side_cm = float(guidance.get("side_cm", 0) or 0)
    if str(guidance.get("side", "")).lower() == "left":
        side_cm *= -1.0
    yaw_rad = math.radians(float(base.rover_pose.get("yaw", 0.0) or 0.0))
    forward_x = math.cos(yaw_rad)
    forward_y = math.sin(yaw_rad)
    right_x = -math.sin(yaw_rad)
    right_y = math.cos(yaw_rad)
    return {
        "x": max(0.0, min(800.0, base.rover_pose["x"] + forward_x * forward_cm + right_x * side_cm)),
        "y": max(0.0, min(800.0, base.rover_pose["y"] + forward_y * forward_cm + right_y * side_cm)),
    }


def fallback_detection_result(payload: Dict[str, Any]) -> Dict[str, Any]:
    detections = [item for item in payload.get("detections", []) if isinstance(item, dict)]
    for category in ("human", "animal", "object", "marker", "fire", "track"):
        matches = [item for item in detections if item.get("category_hint") == category]
        if matches:
            best = max(matches, key=confidence_score)
            label = str(best.get("label", category))
            confidence = confidence_percent_text(best.get("confidence", 0))
            guidance = estimate_detection_guidance(best, payload)
            category_name = "human" if category == "human" else category
            object_phrase = "person" if category == "human" and label == "person" else label
            return {
                "detected": True,
                "category": category_name,
                "message": f"{category_name}: detected {object_phrase} at {confidence} confidence; {guidance['direction']}.",
                "guidance": guidance,
                "label": label,
            }
    return {"detected": False, "category": "", "message": ""}


def build_detection_notes(payload: Dict[str, Any]) -> str:
    detections = [item for item in payload.get("detections", []) if isinstance(item, dict)]
    if not detections:
        return "No objects were detected by Windows YOLO ONNX."
    lines = []
    for detection in detections[:8]:
        label = detection.get("label", "unknown")
        category_hint = detection.get("category_hint", "")
        confidence = confidence_percent_text(detection.get("confidence", ""))
        box = detection.get("box", {})
        lines.append(f"- label={label}, category_hint={category_hint}, confidence={confidence}, box={box}")
    return "Windows YOLO ONNX detections:\n" + "\n".join(lines)


def prompt_for_detection(payload: Dict[str, Any]) -> str:
    return (
        "You are the STASIS rover alert filter. Windows ran YOLO object detection on a Raspberry Pi webcam frame. "
        "Convert the detections into exactly one minified JSON object with schema "
        "{\"detected\": boolean, \"category\": \"human|animal|object|track|fire|marker\", \"message\": string}. "
        "Use human for person/intruder detections. Use animal for wildlife-like detections. "
        "Use object for other relevant objects and include the label in the message. "
        "Return detected false if the detections are irrelevant or too weak. Do not use Markdown.\n\n"
        f"{build_detection_notes(payload)}"
    )


def request_ollama(prompt: str) -> str:
    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={
            "model": OLLAMA_TEXT_MODEL,
            "stream": False,
            "messages": [{"role": "user", "content": prompt}],
            "options": {"temperature": 0, "num_predict": 120},
        },
        timeout=OBJECT_REVIEW_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    return str(data.get("message", {}).get("content", data.get("response", "")))


def request_lmstudio(prompt: str) -> str:
    response = requests.post(
        f"{LMSTUDIO_BASE_URL}/chat/completions",
        json={
            "model": LMSTUDIO_TEXT_MODEL,
            "messages": [
                {"role": "system", "content": "Output strict JSON only."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "max_tokens": 120,
        },
        timeout=OBJECT_REVIEW_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    return str(data["choices"][0]["message"]["content"])


def review_object_detection(payload: Dict[str, Any]) -> Dict[str, Any]:
    provider = OBJECT_REVIEW_PROVIDER
    if provider in {"", "none", "off", "fallback"}:
        return fallback_detection_result(payload)
    prompt = prompt_for_detection(payload)
    try:
        if provider == "ollama":
            text = request_ollama(prompt)
        elif provider in {"lmstudio", "lm_studio"}:
            text = request_lmstudio(prompt)
        else:
            logging.warning("Unknown object review provider %r; using fallback.", provider)
            return fallback_detection_result(payload)
        return base.parse_json_response(text)
    except Exception as exc:
        logging.warning("Local object review model failed; using fallback detection result: %s", exc)
        return fallback_detection_result(payload)


def emit_dashboard_alert(result: Dict[str, Any]) -> None:
    alert_payload = {
        "category": result.get("category", "event"),
        "message": result.get("message", "Activity detected."),
        "image_path": result.get("image_path", ""),
        "action": "stop_and_alert" if result.get("category") in {"human", "fire"} else "alert",
        "x": result.get("x", base.rover_pose["x"]),
        "y": result.get("y", base.rover_pose["y"]),
        "heading": result.get("heading", base.rover_pose["heading"]),
        "label": result.get("label", ""),
        "guidance": result.get("guidance", {}),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    base.socketio.emit("new_alert", alert_payload)
    base.socketio.emit(
        "rover_status",
        {"status": "vision_detected", "message": f"{alert_payload['category']}: {alert_payload['message']}"},
    )


def save_alert_frame(frame: np.ndarray) -> str:
    try:
        return base.save_alert_frame(frame)
    except Exception as exc:
        logging.warning("Could not save object detection alert frame: %s", exc)
        return ""


def process_detections(frame: np.ndarray, detections: list[dict[str, Any]]) -> None:
    global last_object_review_at, last_object_signature

    if not detections:
        return
    signature = ",".join(f"{item.get('label')}:{item.get('category_hint')}" for item in detections[:4])
    now = time.monotonic()
    if signature == last_object_signature and now - last_object_review_at < OBJECT_REVIEW_COOLDOWN:
        return
    last_object_signature = signature
    last_object_review_at = now

    payload = {
        "detections": detections,
        "width": int(frame.shape[1]),
        "height": int(frame.shape[0]),
        "heading": base.rover_pose["heading"],
        "distance_traveled": 0.0,
    }
    analysis = review_object_detection(payload)
    if not analysis.get("detected"):
        return
    fallback_details = fallback_detection_result(payload)
    if fallback_details.get("detected"):
        for key in ("guidance", "label"):
            if not analysis.get(key) and fallback_details.get(key):
                analysis[key] = fallback_details[key]

    image_path = save_alert_frame(frame)
    map_position = estimate_map_position(analysis.get("guidance", {})) if analysis.get("guidance") else base.rover_pose
    result = {
        "type": "vision_result",
        "detected": True,
        "category": analysis.get("category", "event"),
        "message": analysis.get("message", "Object detected."),
        "image_path": image_path,
        "x": map_position["x"],
        "y": map_position["y"],
        "heading": base.rover_pose["heading"],
        "source": "windows_yolo_onnx",
    }
    if analysis.get("guidance"):
        result["guidance"] = analysis["guidance"]
    if analysis.get("label"):
        result["label"] = analysis["label"]
    logging.info("Windows YOLO reviewed as STASIS event: %s", result)
    emit_dashboard_alert(result)
    base.send_rover_command(result)


def windows_object_detection_loop() -> None:
    global detectors

    detectors = []
    common_detector = YoloOnnxDetector(ONNX_MODEL_PATH, ONNX_INPUT_SIZE, COCO_LABELS, "coco", COMMON_ALLOWED_LABELS)
    if common_detector.setup():
        detectors.append(common_detector)

    custom_labels = load_labels(CUSTOM_LABELS_PATH)
    custom_detector = YoloOnnxDetector(
        CUSTOM_ONNX_MODEL_PATH,
        CUSTOM_ONNX_INPUT_SIZE,
        custom_labels,
        "stasis_custom",
        confidence=CUSTOM_ONNX_CONFIDENCE,
    )
    if custom_labels and custom_detector.setup():
        detectors.append(custom_detector)

    if not detectors:
        logging.warning("Windows-side YOLO is inactive until at least one ONNX model and onnxruntime are available.")
        return
    logging.info("Windows-side detection active with %d detector(s).", len(detectors))

    while True:
        time.sleep(max(0.2, OBJECT_ANALYSIS_INTERVAL))
        frame = base.latest_frame
        if frame is None:
            continue
        try:
            working_frame = frame.copy()
            detections: list[dict[str, Any]] = []
            for detector in detectors:
                detections.extend(detector.detect(working_frame))
            detections = filter_scene_detections(detections, working_frame.shape[1], working_frame.shape[0])
            detections.sort(key=confidence_score, reverse=True)
            detections = detections[:ONNX_MAX_DETECTIONS]
            logging.info(
                "Windows YOLO detections: %s",
                [
                    {
                        "detector": item.get("detector"),
                        "label": item.get("label"),
                        "category": item.get("category_hint"),
                        "confidence": item.get("confidence"),
                    }
                    for item in detections[:8]
                ],
            )
            if DRAW_OVERLAY and detections:
                base.latest_frame = draw_detections(working_frame, detections)
                ok_enc, encoded = cv2.imencode(".jpg", base.latest_frame)
                if ok_enc:
                    base.latest_frame_jpeg = encoded.tobytes()
            process_detections(working_frame, detections)
        except Exception as exc:
            logging.exception("Windows YOLO detection failed: %s", exc)


def handle_rover_report(payload: Any) -> None:
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return
    if isinstance(payload, dict) and payload.get("type") == "object_detection":
        if DETECTION_AUTHORITY in {"pi", "rover", "raspberry_pi", "raspberry-pi"}:
            original_handle_rover_report(payload)
            return
        logging.info("Ignoring Pi-side object_detection payload because Windows YOLO is authoritative.")
        return
    original_handle_rover_report(payload)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    base.ALERTS_DIR.mkdir(parents=True, exist_ok=True)
    base.handle_rover_report = handle_rover_report
    if base.CAMERA_SOURCE == "local":
        base.socketio.start_background_task(base.webcam_capture_loop)
    else:
        logging.info("Waiting for Raspberry Pi webcam frames over the rover WebSocket.")
    if DETECTION_AUTHORITY in {"pi", "rover", "raspberry_pi", "raspberry-pi"}:
        logging.info("Pi-side detection authority enabled; Windows YOLO analysis loop is disabled.")
    else:
        base.socketio.start_background_task(windows_object_detection_loop)
    logging.info("Starting STASIS Windows YOLO server on 0.0.0.0:5000.")
    base.socketio.run(base.app, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    main()

"""
STASIS server entry point for Pi-side object detection plus local text-model review.

Run this instead of security_rover_server_windows.py when the Raspberry Pi is
using rover_client_object_detection.py. The normal dashboard, command routing,
telemetry, camera feed, and rover decision flow are reused from the existing
server. This wrapper only adds support for object_detection messages and asks a
local Qwen-style text model through Ollama or LM Studio to turn detections into
STASIS alert JSON.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict

import cv2
import numpy as np
import requests

import security_rover_server_windows as base

OBJECT_REVIEW_PROVIDER = os.getenv("STASIS_OBJECT_REVIEW_PROVIDER", "ollama").strip().lower()
OBJECT_REVIEW_TIMEOUT = float(os.getenv("STASIS_OBJECT_REVIEW_TIMEOUT", "20"))
OBJECT_REVIEW_COOLDOWN = float(os.getenv("STASIS_OBJECT_REVIEW_COOLDOWN", "8"))
OLLAMA_BASE_URL = os.getenv("STASIS_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_TEXT_MODEL = os.getenv("STASIS_OLLAMA_TEXT_MODEL", "qwen2.5:0.5b")
LMSTUDIO_BASE_URL = os.getenv("STASIS_LMSTUDIO_URL", "http://127.0.0.1:1234/v1").rstrip("/")
LMSTUDIO_TEXT_MODEL = os.getenv("STASIS_LMSTUDIO_TEXT_MODEL", "qwen2.5-0.5b-instruct")

last_object_signature = ""
last_object_review_at = 0.0
original_handle_rover_report = base.handle_rover_report


def decode_detection_frame(payload: Dict[str, Any]) -> Any | None:
    if payload.get("format") != "jpeg" or not payload.get("image_b64"):
        return None
    try:
        raw = base64.b64decode(str(payload["image_b64"]), validate=True)
        image_array = np.frombuffer(raw, dtype=np.uint8)
        return cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    except Exception as exc:
        logging.warning("Could not decode object detection frame: %s", exc)
        return None


def save_detection_frame(payload: Dict[str, Any]) -> str:
    frame = decode_detection_frame(payload)
    if frame is None:
        frame = base.latest_frame
    if frame is None:
        return ""
    try:
        return base.save_alert_frame(frame)
    except Exception as exc:
        logging.warning("Could not save object detection alert frame: %s", exc)
        return ""


def build_detection_notes(payload: Dict[str, Any]) -> str:
    detections = payload.get("detections", [])
    if not isinstance(detections, list) or not detections:
        return "No COCO objects were detected by the Raspberry Pi."
    lines = []
    for detection in detections[:8]:
        if not isinstance(detection, dict):
            continue
        label = detection.get("label", "unknown")
        category_hint = detection.get("category_hint", "")
        confidence = detection.get("confidence", "")
        box = detection.get("box", {})
        lines.append(f"- label={label}, category_hint={category_hint}, confidence={confidence}, box={box}")
    return "Raspberry Pi OpenCV COCO detections:\n" + "\n".join(lines)


def prompt_for_detection(payload: Dict[str, Any]) -> str:
    return (
        "You are the STASIS rover alert filter. A Raspberry Pi ran OpenCV COCO object detection. "
        "Convert the detections into exactly one minified JSON object with schema "
        "{\"detected\": boolean, \"category\": \"human|animal|track|fire|marker\", \"message\": string}. "
        "Use human for person/intruder detections. Use animal for wildlife-like detections. "
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


def fallback_detection_result(payload: Dict[str, Any]) -> Dict[str, Any]:
    detections = [item for item in payload.get("detections", []) if isinstance(item, dict)]
    for category in ("human", "animal", "fire", "marker", "track"):
        matches = [item for item in detections if item.get("category_hint") == category]
        if matches:
            best = max(matches, key=lambda item: float(item.get("confidence", 0)))
            label = str(best.get("label", category))
            confidence = float(best.get("confidence", 0))
            return {
                "detected": True,
                "category": category,
                "message": f"{category}: Pi OpenCV detected {label} at {confidence:.2f} confidence.",
            }
    return {"detected": False, "category": "", "message": ""}


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


def handle_object_detection(payload: Dict[str, Any]) -> None:
    global last_object_review_at, last_object_signature

    detections = payload.get("detections", [])
    if not isinstance(detections, list):
        return
    signature = ",".join(
        f"{item.get('label')}:{item.get('category_hint')}" for item in detections[:4] if isinstance(item, dict)
    )
    now = time.monotonic()
    if signature and signature == last_object_signature and now - last_object_review_at < OBJECT_REVIEW_COOLDOWN:
        return
    last_object_signature = signature
    last_object_review_at = now

    frame = decode_detection_frame(payload)
    if frame is not None:
        base.latest_frame = frame
        base.latest_frame_metadata = {
            "source": "rover_object_detection",
            "width": payload.get("width"),
            "height": payload.get("height"),
            "captured_at": payload.get("captured_at"),
            "received_at": time.time(),
        }
        base.socketio.emit("camera_status", {"source": "rover", "connected": True})

    analysis = review_object_detection(payload)
    if not analysis.get("detected"):
        return

    image_path = save_detection_frame(payload)
    result = {
        "type": "vision_result",
        "detected": True,
        "category": analysis.get("category", "event"),
        "message": analysis.get("message", "Object detected."),
        "image_path": image_path,
        "x": base.rover_pose["x"],
        "y": base.rover_pose["y"],
        "heading": base.rover_pose["heading"],
        "source": "pi_opencv_coco_local_text_model",
    }
    if analysis.get("marker"):
        result["marker"] = analysis["marker"]
    logging.info("Object detection reviewed as STASIS event: %s", result)
    base.send_rover_command(result)


def handle_rover_report(payload: Any) -> None:
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return
    if isinstance(payload, dict) and payload.get("type") == "object_detection":
        handle_object_detection(payload)
        return
    original_handle_rover_report(payload)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    base.ALERTS_DIR.mkdir(parents=True, exist_ok=True)
    base.handle_rover_report = handle_rover_report
    if base.CAMERA_SOURCE == "local":
        base.socketio.start_background_task(base.webcam_capture_loop)
    else:
        logging.info("Waiting for Raspberry Pi webcam frames and Pi-side object detections.")
    logging.info("Starting STASIS object-detection server on 0.0.0.0:5000 using %s review.", OBJECT_REVIEW_PROVIDER)
    base.socketio.run(base.app, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    main()

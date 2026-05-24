"""
STASIS Raspberry Pi rover client with local OpenCV object detection.

This entry point keeps the normal rover behavior from rover_client.py, but adds a
Core-Electronics-style COCO detector on the Pi. The Pi still streams camera
frames to the Windows dashboard, and it also sends compact object_detection
notes when target objects are seen. The server can then ask a local text model
such as Qwen through Ollama or LM Studio to decide what STASIS alert to emit.
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import signal
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import rover_client as base


COCO_TO_STASIS = {
    "person": "human",
    "bird": "animal",
    "cat": "animal",
    "dog": "animal",
    "horse": "animal",
    "sheep": "animal",
    "cow": "animal",
    "elephant": "animal",
    "bear": "animal",
    "zebra": "animal",
    "giraffe": "animal",
}

IMPORTANT_OBJECTS = {
    "backpack",
    "umbrella",
    "handbag",
    "suitcase",
    "bottle",
    "cup",
    "chair",
    "potted plant",
    "cell phone",
    "book",
    "scissors",
    "teddy bear",
}


@dataclass
class ObjectDetectionConfig:
    enabled: bool = True
    class_names_path: str = "models/coco.names"
    config_path: str = "models/ssd_mobilenet_v3_large_coco_2020_01_14.pbtxt"
    weights_path: str = "models/frozen_inference_graph.pb"
    confidence_threshold: float = 55.0
    nms_threshold: float = 20.0
    input_size: int = 320
    target_classes: list[str] = field(default_factory=list)
    overlay_enabled: bool = True
    red_strip_enabled: bool = True
    red_strip_min_area: int = 900
    stream_interval_seconds: float = 0.25
    upload_interval_seconds: float = 2.0
    alert_cooldown_seconds: float = 8.0
    send_empty_results: bool = False


class CocoObjectDetector:
    def __init__(self, config: ObjectDetectionConfig, root: Path) -> None:
        self.config = config
        self.root = root
        self.class_names: list[str] = []
        self.model: Any = None

    def _resolve(self, value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else self.root / path

    @staticmethod
    def _ratio(value: float) -> float:
        value = float(value)
        if value > 1.0:
            value /= 100.0
        return max(0.0, min(1.0, value))

    def setup(self) -> bool:
        if not self.config.enabled:
            logging.info("Pi-side object detection disabled by config.")
            return False
        try:
            import cv2
        except ImportError:
            logging.error("opencv-python is required for Pi-side object detection.")
            return False

        names_path = self._resolve(self.config.class_names_path)
        config_path = self._resolve(self.config.config_path)
        weights_path = self._resolve(self.config.weights_path)
        missing = [str(path) for path in (names_path, config_path, weights_path) if not path.exists()]
        if missing:
            logging.warning("Object detector model files missing: %s", ", ".join(missing))
            return False

        self.class_names = [line.strip() for line in names_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.model = cv2.dnn_DetectionModel(str(weights_path), str(config_path))
        self.model.setInputSize(self.config.input_size, self.config.input_size)
        self.model.setInputScale(1.0 / 127.5)
        self.model.setInputMean((127.5, 127.5, 127.5))
        self.model.setInputSwapRB(True)
        logging.info("Pi-side COCO object detector loaded with %d classes.", len(self.class_names))
        return True

    def detect(self, frame: Any) -> list[dict[str, Any]]:
        if self.model is None:
            return []
        class_ids, confidences, boxes = self.model.detect(
            frame,
            confThreshold=self._ratio(self.config.confidence_threshold),
            nmsThreshold=self._ratio(self.config.nms_threshold),
        )
        detections: list[dict[str, Any]] = []
        target_classes = {item.lower() for item in self.config.target_classes}
        if len(class_ids) == 0:
            return detections
        for class_id, confidence, box in zip(class_ids.flatten(), confidences.flatten(), boxes):
            index = int(class_id) - 1
            label = self.class_names[index] if 0 <= index < len(self.class_names) else str(class_id)
            label_lower = label.lower()
            if target_classes and label_lower not in target_classes:
                continue
            x, y, width, height = [int(value) for value in box]
            category_hint = COCO_TO_STASIS.get(label_lower, "object" if label_lower in IMPORTANT_OBJECTS or not target_classes else "")
            detections.append(
                {
                    "label": label_lower,
                    "category_hint": category_hint,
                    "confidence": round(float(confidence), 3),
                    "box": {"x": x, "y": y, "width": width, "height": height},
                }
            )
        detections.sort(key=lambda item: item["confidence"], reverse=True)
        return detections


class RedStripDetector:
    def __init__(self, config: ObjectDetectionConfig) -> None:
        self.config = config

    def detect(self, frame: Any) -> list[dict[str, Any]]:
        if not self.config.red_strip_enabled:
            return []
        import cv2

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lower_red_a = (0, 80, 70)
        upper_red_a = (12, 255, 255)
        lower_red_b = (170, 80, 70)
        upper_red_b = (180, 255, 255)
        mask = cv2.inRange(hsv, lower_red_a, upper_red_a) | cv2.inRange(hsv, lower_red_b, upper_red_b)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, None, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, None, iterations=2)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        detections: list[dict[str, Any]] = []
        for contour in contours:
            area = float(cv2.contourArea(contour))
            if area < float(self.config.red_strip_min_area):
                continue
            x, y, width, height = cv2.boundingRect(contour)
            if width < 12 or height < 8:
                continue
            detections.append(
                {
                    "label": "red strip",
                    "category_hint": "marker",
                    "confidence": min(0.99, round(area / max(1.0, frame.shape[0] * frame.shape[1] * 0.08), 3)),
                    "box": {"x": int(x), "y": int(y), "width": int(width), "height": int(height)},
                    "marker": "red_strip",
                }
            )
        detections.sort(key=lambda item: item["confidence"], reverse=True)
        return detections[:3]


def load_object_detection_config(path: Path | None) -> ObjectDetectionConfig:
    config = ObjectDetectionConfig()
    if path is None or not path.exists():
        return config
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logging.warning("Could not read object_detection config from %s: %s", path, exc)
        return config
    section = data.get("object_detection", {}) if isinstance(data, dict) else {}
    if not isinstance(section, dict):
        return config
    for key, value in section.items():
        if hasattr(config, key):
            setattr(config, key, value)
    return config


class ObjectDetectionRoverClient(base.RoverClient):
    def __init__(self, config: base.RoverConfig, hardware: base.HardwareBase, detector_config: ObjectDetectionConfig, root: Path) -> None:
        super().__init__(config, hardware)
        self.detector = CocoObjectDetector(detector_config, root)
        self.red_strip_detector = RedStripDetector(detector_config)
        self.detector_config = detector_config
        self.detector_ready = False
        self.last_detection_sent = 0.0
        self.last_detection_signature = ""
        self.latest_detections: list[dict[str, Any]] = []
        self.detection_lock = threading.Lock()

    def run(self) -> None:
        self.detector_ready = self.detector.setup()
        super().run()

    def _send_object_detection(self, detections: list[dict[str, Any]], frame: Any) -> None:
        now = time.monotonic()
        signature = ",".join(f"{item['label']}:{item['category_hint']}" for item in detections[:4])
        if detections and signature == self.last_detection_signature and now - self.last_detection_sent < self.detector_config.alert_cooldown_seconds:
            return
        if not detections and not self.detector_config.send_empty_results:
            return

        encoded_ok, encoded = self._encode_frame(frame)
        payload: dict[str, Any] = {
            "type": "object_detection",
            "source": "pi_opencv_coco",
            "detections": detections,
            "captured_at": time.time(),
            "heading": self.last_heading,
            "distance_traveled": self.distance_traveled_cm,
        }
        if encoded_ok:
            payload.update(
                {
                    "format": "jpeg",
                    "image_b64": base64.b64encode(encoded.tobytes()).decode("ascii"),
                    "width": int(frame.shape[1]),
                    "height": int(frame.shape[0]),
                }
            )
        self.send_json(payload)
        self.last_detection_sent = now
        self.last_detection_signature = signature

    def _overlay_detections(self, frame: Any) -> Any:
        if not self.detector_config.overlay_enabled:
            return frame
        import cv2

        with self.detection_lock:
            detections = list(self.latest_detections)
        overlay = frame.copy()
        for item in detections[:12]:
            box = item.get("box", {})
            try:
                x = int(box.get("x", 0))
                y = int(box.get("y", 0))
                width = int(box.get("width", 0))
                height = int(box.get("height", 0))
            except Exception:
                continue
            if width <= 0 or height <= 0:
                continue
            label = str(item.get("label", "object"))
            confidence = float(item.get("confidence", 0))
            confidence_percent = confidence if confidence > 1.0 else confidence * 100.0
            color = (0, 255, 0) if item.get("category_hint") != "marker" else (0, 0, 255)
            cv2.rectangle(overlay, (x, y), (x + width, y + height), color, 2)
            caption = f"{label} {confidence_percent:.0f}%"
            cv2.putText(overlay, caption, (x, max(18, y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        return overlay

    def _encode_frame(self, frame: Any) -> tuple[bool, Any]:
        import cv2

        quality = max(30, min(95, int(self.config.camera.jpeg_quality)))
        return cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])

    def camera_loop(self) -> None:
        camera = self.config.camera
        if not camera.enabled:
            logging.info("Raspberry Pi webcam streaming disabled by config.")
            return
        try:
            import cv2
        except ImportError:
            logging.error("opencv-python is required for Pi webcam streaming and object detection.")
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
            logging.info("Streaming Pi webcam smoothly at %sx%s; object detection runs on a slower side interval.", camera.width, camera.height)
            last_detection_run = 0.0
            last_stream_sent = 0.0

            while not self.stop_requested.is_set():
                ok, frame = cap.read()
                if not ok or frame is None:
                    logging.warning("Pi webcam read failed; reconnecting camera.")
                    break

                if self.connected.is_set():
                    now = time.monotonic()
                    stream_interval = max(0.05, float(self.detector_config.stream_interval_seconds or camera.upload_interval_seconds))
                    if now - last_stream_sent >= stream_interval:
                        display_frame = self._overlay_detections(frame)
                        encoded_ok, encoded = self._encode_frame(display_frame)
                        if encoded_ok:
                            self.send_json(
                                {
                                    "type": "camera_frame",
                                    "format": "jpeg",
                                    "image_b64": base64.b64encode(encoded.tobytes()).decode("ascii"),
                                    "width": int(display_frame.shape[1]),
                                    "height": int(display_frame.shape[0]),
                                    "captured_at": time.time(),
                                }
                            )
                            last_stream_sent = now
                    detection_interval = max(0.2, float(self.detector_config.upload_interval_seconds))
                    if now - last_detection_run >= detection_interval:
                        detections = self.detector.detect(frame) if self.detector_ready else []
                        detections.extend(self.red_strip_detector.detect(frame))
                        with self.detection_lock:
                            self.latest_detections = detections
                        self._send_object_detection(detections, frame)
                        last_detection_run = now

                time.sleep(0.02)

            cap.release()
            time.sleep(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="STASIS Raspberry Pi rover client with Pi-side object detection")
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
    config = base.read_config(args.config)
    if args.server:
        config.server_host = args.server
    if args.port:
        config.server_port = args.port
    if args.rover_id:
        config.rover_id = args.rover_id
    if args.simulate:
        config.simulate = True
    if not config.server_host:
        raise SystemExit("STASIS server host ip is unspecified. Use config.json or --server <IP>.")

    hardware: base.HardwareBase = base.SimulatedHardware(config) if config.simulate else base.RealRoverHardware(config)
    detector_config = load_object_detection_config(args.config)
    client = ObjectDetectionRoverClient(config, hardware, detector_config, Path(__file__).resolve().parent)
    signal.signal(signal.SIGINT, client.request_stop)
    signal.signal(signal.SIGTERM, client.request_stop)
    try:
        client.run()
    except Exception as exc:
        logging.critical("STASIS object-detection rover client terminated: %s", exc)
    finally:
        logging.info("STASIS object-detection client session terminated safely.")


if __name__ == "__main__":
    main()

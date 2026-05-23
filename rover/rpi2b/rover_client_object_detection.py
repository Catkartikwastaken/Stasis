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


@dataclass
class ObjectDetectionConfig:
    enabled: bool = True
    class_names_path: str = "models/coco.names"
    config_path: str = "models/ssd_mobilenet_v3_large_coco_2020_01_14.pbtxt"
    weights_path: str = "models/frozen_inference_graph.pb"
    confidence_threshold: float = 0.45
    nms_threshold: float = 0.20
    input_size: int = 320
    target_classes: list[str] = field(default_factory=lambda: ["person", "bird", "cat", "dog", "horse", "sheep", "cow", "bear"])
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
            confThreshold=float(self.config.confidence_threshold),
            nmsThreshold=float(self.config.nms_threshold),
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
            detections.append(
                {
                    "label": label_lower,
                    "category_hint": COCO_TO_STASIS.get(label_lower, ""),
                    "confidence": round(float(confidence), 3),
                    "box": {"x": x, "y": y, "width": width, "height": height},
                }
            )
        detections.sort(key=lambda item: item["confidence"], reverse=True)
        return detections


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
        self.detector_config = detector_config
        self.detector_ready = False
        self.last_detection_sent = 0.0
        self.last_detection_signature = ""

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
            logging.info("Streaming Pi webcam with object detection at %sx%s.", camera.width, camera.height)

            while not self.stop_requested.is_set():
                ok, frame = cap.read()
                if not ok or frame is None:
                    logging.warning("Pi webcam read failed; reconnecting camera.")
                    break

                if self.connected.is_set():
                    encoded_ok, encoded = self._encode_frame(frame)
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
                    detections = self.detector.detect(frame) if self.detector_ready else []
                    self._send_object_detection(detections, frame)

                interval = self.detector_config.upload_interval_seconds or camera.upload_interval_seconds
                time.sleep(max(0.1, float(interval)))

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

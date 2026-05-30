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
import importlib
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

BACKGROUND_LABELS = {
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

HUMAN_LABELS = {"person", "human", "man", "woman", "boy", "girl", "face", "head"}
MARKER_LABELS = {"green strip", "green_strip"}
ANIMAL_LABELS = set(COCO_TO_STASIS)
ANIMAL_LABELS.discard("person")


@dataclass
class ObjectDetectionConfig:
    enabled: bool = True
    backend: str = "opencv"
    yolo_model_path: str = "models/yolo11n_ncnn_model"
    class_names_path: str = "models/coco.names"
    config_path: str = "models/ssd_mobilenet_v3_large_coco_2020_01_14.pbtxt"
    weights_path: str = "models/frozen_inference_graph.pb"
    confidence_threshold: float = 55.0
    nms_threshold: float = 20.0
    input_size: int = 320
    target_classes: list[str] = field(default_factory=list)
    common_detection_enabled: bool = True
    common_target_classes: list[str] = field(default_factory=lambda: ["person", "cell phone"])
    ignored_classes: list[str] = field(default_factory=lambda: sorted(BACKGROUND_LABELS))
    min_box_area_percent: float = 1.0
    max_box_area_percent: float = 85.0
    overlay_enabled: bool = True
    green_strip_enabled: bool = False
    green_strip_min_area: int = 2500
    green_strip_min_aspect_ratio: float = 4.0
    green_strip_min_fill_ratio: float = 0.7
    stream_interval_seconds: float = 0.12
    stream_jpeg_quality: int = 50
    upload_interval_seconds: float = 2.0
    common_detection_every_n: int = 2
    alert_cooldown_seconds: float = 8.0
    send_empty_results: bool = False


def category_for_label(label: str, allow_general_objects: bool = True) -> str:
    label = label.strip().lower()
    if label in MARKER_LABELS:
        return "marker"
    if label in HUMAN_LABELS:
        return "human"
    if label in ANIMAL_LABELS:
        return "animal"
    if label in BACKGROUND_LABELS:
        return ""
    if label in IMPORTANT_OBJECTS or allow_general_objects:
        return "object"
    return ""


def label_key(label: str) -> str:
    return label.strip().lower().replace("_", " ")


def should_keep_detection(label: str, box: dict[str, int], frame_width: int, frame_height: int, config: ObjectDetectionConfig) -> bool:
    label = label_key(label)
    ignored = {label_key(item) for item in config.ignored_classes}
    if label in ignored:
        return False
    area_percent = (float(box.get("width", 0)) * float(box.get("height", 0)) * 100.0) / max(1.0, float(frame_width * frame_height))
    return float(config.min_box_area_percent) <= area_percent <= float(config.max_box_area_percent)


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
        target_classes = {label_key(item) for item in self.config.target_classes}
        if len(class_ids) == 0:
            return detections
        for class_id, confidence, box in zip(class_ids.flatten(), confidences.flatten(), boxes):
            index = int(class_id) - 1
            label = self.class_names[index] if 0 <= index < len(self.class_names) else str(class_id)
            label_lower = label_key(label)
            if target_classes and label_lower not in target_classes:
                continue
            x, y, width, height = [int(value) for value in box]
            bbox = {"x": x, "y": y, "width": width, "height": height}
            if not should_keep_detection(label_lower, bbox, int(frame.shape[1]), int(frame.shape[0]), self.config):
                continue
            category_hint = category_for_label(label_lower, allow_general_objects=not bool(target_classes))
            if not category_hint:
                continue
            detections.append(
                {
                    "label": label_lower,
                    "category_hint": category_hint,
                    "detector": "coco",
                    "confidence": round(float(confidence), 3),
                    "box": bbox,
                }
            )
        detections.sort(key=lambda item: item["confidence"], reverse=True)
        return detections


class YoloObjectDetector:
    def __init__(self, config: ObjectDetectionConfig, root: Path) -> None:
        self.config = config
        self.root = root
        self.model: Any = None
        self.ncnn_net: Any = None
        self.ncnn_names: dict[int, str] = {}
        self.ncnn_param_path: Path | None = None
        self.ncnn_bin_path: Path | None = None

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
        model_path = self._resolve(self.config.yolo_model_path)
        if not model_path.exists():
            logging.warning("YOLO model path missing: %s", model_path)
            return False

        if model_path.is_dir() and (model_path / "model.ncnn.param").exists() and (model_path / "model.ncnn.bin").exists():
            return self._setup_ncnn(model_path)

        try:
            from ultralytics import YOLO
        except ImportError:
            logging.error(
                "ultralytics is required for .pt/.onnx YOLO model loading. "
                "For Pi without ultralytics, use an exported NCNN folder containing model.ncnn.param and model.ncnn.bin."
            )
            return False

        self.model = YOLO(str(model_path))
        names = {str(value).lower() for value in getattr(self.model, "names", {}).values()}
        if "person" not in names:
            logging.warning(
                "YOLO model at %s does not expose the COCO 'person' class. "
                "Human detection will be poor; export a COCO model such as yolo11n.pt to NCNN.",
                model_path,
            )
        logging.info("Pi-side YOLO object detector loaded from %s.", model_path)
        return True

    def _setup_ncnn(self, model_path: Path) -> bool:
        try:
            ncnn = importlib.import_module("ncnn")
        except ImportError:
            logging.error("ncnn is required for direct NCNN model loading. Install with: python -m pip install ncnn")
            return False

        self.ncnn_param_path = model_path / "model.ncnn.param"
        self.ncnn_bin_path = model_path / "model.ncnn.bin"
        self.ncnn_names = self._load_ncnn_names(model_path / "metadata.yaml")
        self.ncnn_net = ncnn.Net()
        self.ncnn_net.load_param(str(self.ncnn_param_path))
        self.ncnn_net.load_model(str(self.ncnn_bin_path))
        logging.info("Pi-side NCNN YOLO detector loaded from %s with %d classes.", model_path, len(self.ncnn_names))
        return True

    @staticmethod
    def _load_ncnn_names(path: Path) -> dict[int, str]:
        if not path.exists():
            return {}
        names: dict[int, str] = {}
        in_names = False
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.rstrip()
            if line.strip() == "names:":
                in_names = True
                continue
            if in_names and line and not line.startswith(" "):
                break
            if in_names and ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                if key.isdigit():
                    names[int(key)] = value.strip().strip("'\"")
        return names

    def _detect_ncnn(self, frame: Any) -> list[dict[str, Any]]:
        if self.ncnn_net is None:
            return []
        import cv2
        import ncnn
        import numpy as np

        input_size = int(self.config.input_size)
        frame_height, frame_width = int(frame.shape[0]), int(frame.shape[1])
        mat = ncnn.Mat.from_pixels_resize(
            frame,
            ncnn.Mat.PixelType.PIXEL_BGR2RGB,
            frame_width,
            frame_height,
            input_size,
            input_size,
        )
        mat.substract_mean_normalize([], [1.0 / 255.0, 1.0 / 255.0, 1.0 / 255.0])

        with self.ncnn_net.create_extractor() as ex:
            ex.input("in0", mat)
            _, out0 = ex.extract("out0")

        raw = np.array(out0)
        if raw.ndim != 2:
            raw = raw.reshape(raw.shape[0], -1)
        if raw.shape[0] < raw.shape[1]:
            raw = raw.T
        if raw.shape[1] < 5:
            return []

        boxes: list[list[int]] = []
        scores: list[float] = []
        class_ids: list[int] = []
        target_classes = {label_key(item) for item in self.config.target_classes}
        threshold = self._ratio(self.config.confidence_threshold)

        for row in raw:
            class_scores = row[4:]
            class_id = int(np.argmax(class_scores))
            confidence = float(class_scores[class_id])
            if confidence < threshold:
                continue
            label = label_key(self.ncnn_names.get(class_id, str(class_id)))
            if target_classes and label not in target_classes:
                continue
            x1, y1, x2, y2 = [float(value) for value in row[:4]]
            if x2 <= x1 or y2 <= y1:
                cx, cy, width, height = x1, y1, x2, y2
                x1 = cx - width / 2.0
                y1 = cy - height / 2.0
                x2 = cx + width / 2.0
                y2 = cy + height / 2.0
            x = int(x1 * frame_width / input_size)
            y = int(y1 * frame_height / input_size)
            w = int((x2 - x1) * frame_width / input_size)
            h = int((y2 - y1) * frame_height / input_size)
            bbox = {
                "x": max(0, min(frame_width - 1, x)),
                "y": max(0, min(frame_height - 1, y)),
                "width": max(1, min(frame_width, w)),
                "height": max(1, min(frame_height, h)),
            }
            if not should_keep_detection(label, bbox, frame_width, frame_height, self.config):
                continue
            boxes.append([bbox["x"], bbox["y"], bbox["width"], bbox["height"]])
            scores.append(confidence)
            class_ids.append(class_id)

        if not boxes:
            return []

        kept = cv2.dnn.NMSBoxes(boxes, scores, threshold, self._ratio(self.config.nms_threshold))
        kept_indices = [int(i) for i in np.array(kept).flatten()] if len(kept) else []
        detections: list[dict[str, Any]] = []
        for index in kept_indices[:12]:
            label = label_key(self.ncnn_names.get(class_ids[index], str(class_ids[index])))
            category_hint = category_for_label(label, allow_general_objects=True)
            if not category_hint:
                continue
            detections.append(
                {
                    "label": label,
                    "category_hint": category_hint,
                    "detector": "stasis_custom",
                    "confidence": round(float(scores[index]), 3),
                    "box": {"x": boxes[index][0], "y": boxes[index][1], "width": boxes[index][2], "height": boxes[index][3]},
                    **({"marker": "green_strip"} if category_hint == "marker" else {}),
                }
            )
        detections.sort(key=lambda item: item["confidence"], reverse=True)
        return detections

    def detect(self, frame: Any) -> list[dict[str, Any]]:
        if self.ncnn_net is not None:
            return self._detect_ncnn(frame)
        if self.model is None:
            return []
        target_classes = {label_key(item) for item in self.config.target_classes}
        results = self.model.predict(
            source=frame,
            imgsz=int(self.config.input_size),
            conf=self._ratio(self.config.confidence_threshold),
            iou=self._ratio(self.config.nms_threshold),
            verbose=False,
        )
        detections: list[dict[str, Any]] = []
        if not results:
            return detections
        result = results[0]
        names = getattr(result, "names", {}) or {}
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            return detections
        for box in boxes:
            class_id = int(box.cls[0])
            label = label_key(str(names.get(class_id, class_id)))
            if target_classes and label not in target_classes:
                continue
            x1, y1, x2, y2 = [int(value) for value in box.xyxy[0].tolist()]
            confidence = float(box.conf[0])
            bbox = {"x": x1, "y": y1, "width": max(1, x2 - x1), "height": max(1, y2 - y1)}
            if not should_keep_detection(label, bbox, int(frame.shape[1]), int(frame.shape[0]), self.config):
                continue
            category_hint = category_for_label(label, allow_general_objects=True)
            if not category_hint:
                continue
            detections.append(
                {
                    "label": label,
                    "category_hint": category_hint,
                    "detector": "stasis_custom",
                    "confidence": round(confidence, 3),
                    "box": bbox,
                    **({"marker": "green_strip"} if category_hint == "marker" else {}),
                }
            )
        detections.sort(key=lambda item: item["confidence"], reverse=True)
        return detections


class CombinedObjectDetector:
    def __init__(self, config: ObjectDetectionConfig, root: Path) -> None:
        self.config = config
        self.root = root
        self.custom_detector = YoloObjectDetector(config, root)
        self.common_detector: CocoObjectDetector | None = None
        self.detect_count = 0

    def setup(self) -> bool:
        custom_ready = self.custom_detector.setup()
        common_ready = False
        if self.config.common_detection_enabled:
            common_config = ObjectDetectionConfig(**self.config.__dict__)
            common_config.backend = "opencv"
            common_config.target_classes = list(self.config.common_target_classes or ["person", "cell phone"])
            common_config.ignored_classes = []
            self.common_detector = CocoObjectDetector(common_config, self.root)
            common_ready = self.common_detector.setup()
        if custom_ready and common_ready:
            logging.info("Combined detector ready: custom YOLO plus common person/cell-phone COCO.")
        elif custom_ready:
            logging.warning("Combined detector running custom YOLO only; common COCO detector unavailable.")
        elif common_ready:
            logging.warning("Combined detector running common COCO only; custom YOLO detector unavailable.")
        return custom_ready or common_ready

    def detect(self, frame: Any) -> list[dict[str, Any]]:
        self.detect_count += 1
        detections = self.custom_detector.detect(frame)
        common_every = max(1, int(getattr(self.config, "common_detection_every_n", 1) or 1))
        if self.common_detector is not None and self.detect_count % common_every == 0:
            detections.extend(self.common_detector.detect(frame))
        detections.sort(key=lambda item: item["confidence"], reverse=True)
        return detections[:12]


class GreenStripDetector:
    def __init__(self, config: ObjectDetectionConfig) -> None:
        self.config = config

    def detect(self, frame: Any) -> list[dict[str, Any]]:
        if not self.config.green_strip_enabled:
            return []
        import cv2

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lower_green = (35, 70, 60)
        upper_green = (90, 255, 255)
        mask = cv2.inRange(hsv, lower_green, upper_green)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, None, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, None, iterations=2)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        detections: list[dict[str, Any]] = []
        for contour in contours:
            area = float(cv2.contourArea(contour))
            if area < float(self.config.green_strip_min_area):
                continue
            x, y, width, height = cv2.boundingRect(contour)
            if width < 12 or height < 8:
                continue
            aspect_ratio = max(width / max(1, height), height / max(1, width))
            if aspect_ratio < float(self.config.green_strip_min_aspect_ratio):
                continue
            crop = mask[y : y + height, x : x + width]
            fill_ratio = float(cv2.countNonZero(crop)) / float(max(1, width * height))
            if fill_ratio < float(self.config.green_strip_min_fill_ratio):
                continue
            detections.append(
                {
                    "label": "green strip",
                    "category_hint": "marker",
                    "detector": "green_strip_color",
                    "confidence": min(0.99, round(max(fill_ratio, area / max(1.0, frame.shape[0] * frame.shape[1] * 0.08)), 3)),
                    "box": {"x": int(x), "y": int(y), "width": int(width), "height": int(height)},
                    "marker": "green_strip",
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
        backend = str(detector_config.backend or "yolo").strip().lower()
        if backend == "combined":
            self.detector = CombinedObjectDetector(detector_config, root)
        elif backend == "yolo":
            self.detector = YoloObjectDetector(detector_config, root)
        else:
            self.detector = CocoObjectDetector(detector_config, root)
        self.green_strip_detector = GreenStripDetector(detector_config)
        self.detector_config = detector_config
        self.detector_ready = False
        self.last_detection_sent = 0.0
        self.last_detection_signature = ""
        self.latest_detections: list[dict[str, Any]] = []
        self.detection_lock = threading.Lock()
        self.latest_frame_for_detection: Any = None
        self.detection_frame_lock = threading.Lock()

    def run(self) -> None:
        self.detector_ready = self.detector.setup()
        threading.Thread(target=self.detection_loop, name="pi-detection-loop", daemon=True).start()
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
            "source": "pi_object_detection",
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

    def _update_detection_frame(self, frame: Any) -> None:
        with self.detection_frame_lock:
            self.latest_frame_for_detection = frame.copy()

    def _get_detection_frame(self) -> Any:
        with self.detection_frame_lock:
            if self.latest_frame_for_detection is None:
                return None
            return self.latest_frame_for_detection.copy()

    def detection_loop(self) -> None:
        while not self.stop_requested.is_set():
            if not self.connected.is_set():
                time.sleep(0.1)
                continue
            frame = self._get_detection_frame()
            if frame is None:
                time.sleep(0.05)
                continue
            detections = self.detector.detect(frame) if self.detector_ready else []
            detections.extend(self.green_strip_detector.detect(frame))
            with self.detection_lock:
                self.latest_detections = detections
            self._send_object_detection(detections, frame)
            time.sleep(max(0.2, float(self.detector_config.upload_interval_seconds)))

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
            color = (0, 255, 0) if item.get("category_hint") != "marker" else (80, 255, 80)
            cv2.rectangle(overlay, (x, y), (x + width, y + height), color, 2)
            caption = f"{label} {confidence_percent:.0f}%"
            cv2.putText(overlay, caption, (x, max(18, y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        return overlay

    def _encode_frame(self, frame: Any, quality: int | None = None) -> tuple[bool, Any]:
        import cv2

        quality = self.config.camera.jpeg_quality if quality is None else quality
        quality = max(30, min(95, int(quality)))
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
            last_stream_sent = 0.0

            while not self.stop_requested.is_set():
                ok, frame = cap.read()
                if not ok or frame is None:
                    logging.warning("Pi webcam read failed; reconnecting camera.")
                    break

                if self.connected.is_set():
                    now = time.monotonic()
                    self._update_detection_frame(frame)
                    stream_interval = max(0.05, float(self.detector_config.stream_interval_seconds or camera.upload_interval_seconds))
                    if now - last_stream_sent >= stream_interval:
                        display_frame = self._overlay_detections(frame)
                        encoded_ok, encoded = self._encode_frame(display_frame, self.detector_config.stream_jpeg_quality)
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


def validate_json_config(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"Config file not found: {path}")
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"Config file is invalid JSON: {path}\n"
            f"Line {exc.lineno}, column {exc.colno}: {exc.msg}\n"
            "Fix config.json first. The object-detection client will not run with safe defaults."
        ) from exc


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=args.log_level.upper(), format="%(asctime)s %(levelname)s %(message)s")
    validate_json_config(args.config)
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

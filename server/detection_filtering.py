"""
Post-processing reliability gate for STASIS object detections.

The model still produces raw boxes. This module decides when a raw box is
trustworthy enough to become a confirmed detection and when it is allowed to
trigger an alert.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict


def _ratio(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if parsed > 1.0:
        parsed /= 100.0
    return max(0.0, min(1.0, parsed))


def _confidence(item: Dict[str, Any]) -> float:
    return _ratio(item.get("confidence", 0), 0.0)


def _label(item: Dict[str, Any]) -> str:
    return str(item.get("label") or item.get("category_hint") or "unknown").strip().lower().replace("_", " ")


def _category(item: Dict[str, Any]) -> str:
    return str(item.get("category_hint") or "object").strip().lower().replace("_", " ")


def _box(item: Dict[str, Any]) -> Dict[str, float]:
    raw = item.get("box") if isinstance(item.get("box"), dict) else {}
    return {
        "x": float(raw.get("x", 0) or 0),
        "y": float(raw.get("y", 0) or 0),
        "width": float(raw.get("width", 0) or 0),
        "height": float(raw.get("height", 0) or 0),
    }


def _box_area_ratio(box: Dict[str, float], frame_width: int, frame_height: int) -> float:
    return (box["width"] * box["height"]) / max(1.0, float(frame_width * frame_height))


def _center(box: Dict[str, float]) -> tuple[float, float]:
    return box["x"] + box["width"] / 2.0, box["y"] + box["height"] / 2.0


def _iou(left: Dict[str, float], right: Dict[str, float]) -> float:
    left_x2 = left["x"] + left["width"]
    left_y2 = left["y"] + left["height"]
    right_x2 = right["x"] + right["width"]
    right_y2 = right["y"] + right["height"]
    inter_w = max(0.0, min(left_x2, right_x2) - max(left["x"], right["x"]))
    inter_h = max(0.0, min(left_y2, right_y2) - max(left["y"], right["y"]))
    inter = inter_w * inter_h
    union = left["width"] * left["height"] + right["width"] * right["height"] - inter
    return inter / max(1.0, union)


@dataclass
class DetectionFilterConfig:
    human_confidence_threshold: float = 0.70
    object_confidence_threshold: float = 0.75
    min_consecutive_frames: int = 5
    min_box_area_ratio: float = 0.02
    edge_margin_top_ratio: float = 0.10
    edge_margin_bottom_ratio: float = 0.10
    edge_margin_left_ratio: float = 0.05
    edge_margin_right_ratio: float = 0.05
    stability_iou_threshold: float = 0.30
    stability_center_shift_ratio: float = 0.16
    stability_size_change_ratio: float = 0.55
    alert_cooldown_seconds: float = 10.0
    max_track_missing_frames: int = 2
    max_tracks: int = 32

    @classmethod
    def from_mapping(cls, values: Dict[str, Any]) -> "DetectionFilterConfig":
        config = cls()
        for key, value in values.items():
            if hasattr(config, key):
                setattr(config, key, value)
        config.human_confidence_threshold = _ratio(config.human_confidence_threshold, 0.70)
        config.object_confidence_threshold = _ratio(config.object_confidence_threshold, 0.75)
        config.min_box_area_ratio = _ratio(config.min_box_area_ratio, 0.02)
        config.edge_margin_top_ratio = _ratio(config.edge_margin_top_ratio, 0.10)
        config.edge_margin_bottom_ratio = _ratio(config.edge_margin_bottom_ratio, 0.10)
        config.edge_margin_left_ratio = _ratio(config.edge_margin_left_ratio, 0.05)
        config.edge_margin_right_ratio = _ratio(config.edge_margin_right_ratio, 0.05)
        config.stability_iou_threshold = _ratio(config.stability_iou_threshold, 0.30)
        config.stability_center_shift_ratio = _ratio(config.stability_center_shift_ratio, 0.16)
        config.stability_size_change_ratio = _ratio(config.stability_size_change_ratio, 0.55)
        config.min_consecutive_frames = max(1, int(config.min_consecutive_frames))
        config.max_track_missing_frames = max(0, int(config.max_track_missing_frames))
        config.max_tracks = max(1, int(config.max_tracks))
        config.alert_cooldown_seconds = max(0.0, float(config.alert_cooldown_seconds))
        return config


@dataclass
class DetectionTrack:
    track_id: str
    label: str
    category: str
    box: Dict[str, float]
    consecutive_frames: int = 1
    missing_frames: int = 0
    last_seen: float = field(default_factory=time.monotonic)
    last_alert_at: float = 0.0
    confirmed: bool = False


class DetectionPostProcessor:
    def __init__(self, config: DetectionFilterConfig | None = None) -> None:
        self.config = config or DetectionFilterConfig()
        self.tracks: dict[str, DetectionTrack] = {}
        self._next_id = 1

    def process(self, detections: list[Dict[str, Any]], frame_width: int, frame_height: int) -> Dict[str, list[Dict[str, Any]]]:
        now = time.monotonic()
        candidates: list[Dict[str, Any]] = []
        confirmed: list[Dict[str, Any]] = []
        alertable: list[Dict[str, Any]] = []
        rejected: list[Dict[str, Any]] = []
        seen_tracks: set[str] = set()

        for item in detections:
            if not isinstance(item, dict):
                continue
            reason = self._first_rejection_reason(item, frame_width, frame_height)
            if reason:
                self._append_rejected(rejected, item, reason)
                continue

            box = _box(item)
            track = self._match_track(item, box, frame_width, frame_height)
            if track is None:
                track = self._new_track(item, box, now)
            else:
                track.box = box
                track.consecutive_frames += 1
                track.missing_frames = 0
                track.last_seen = now

            seen_tracks.add(track.track_id)
            enriched = self._enrich(item, track)
            if track.consecutive_frames < self.config.min_consecutive_frames:
                enriched["state"] = "candidate"
                enriched["reason"] = "insufficient_persistence"
                self._log_rejection(enriched, "Insufficient persistence")
                candidates.append(enriched)
                continue

            track.confirmed = True
            enriched["state"] = "confirmed"
            enriched["reason"] = "confirmed"
            confirmed.append(enriched)

            if now - track.last_alert_at < self.config.alert_cooldown_seconds:
                enriched["alert_allowed"] = False
                enriched["reason"] = "duplicate_during_cooldown"
                self._log_rejection(enriched, "Duplicate during cooldown")
                continue

            track.last_alert_at = now
            enriched["alert_allowed"] = True
            alertable.append(enriched)

        self._age_tracks(seen_tracks)
        self._trim_tracks()
        return {
            "candidates": candidates,
            "confirmed": confirmed,
            "alertable": alertable,
            "rejected": rejected,
        }

    def _first_rejection_reason(self, item: Dict[str, Any], frame_width: int, frame_height: int) -> str:
        category = _category(item)
        confidence = _confidence(item)
        threshold = self.config.human_confidence_threshold if category == "human" else self.config.object_confidence_threshold
        if confidence < threshold:
            return "low_confidence"

        box = _box(item)
        if box["width"] <= 0 or box["height"] <= 0:
            return "too_small"
        if _box_area_ratio(box, frame_width, frame_height) < self.config.min_box_area_ratio:
            return "too_small"

        center_x, center_y = _center(box)
        if center_y < frame_height * self.config.edge_margin_top_ratio:
            return "edge_zone"
        if center_y > frame_height * (1.0 - self.config.edge_margin_bottom_ratio):
            return "edge_zone"
        if center_x < frame_width * self.config.edge_margin_left_ratio:
            return "edge_zone"
        if center_x > frame_width * (1.0 - self.config.edge_margin_right_ratio):
            return "edge_zone"
        return ""

    def _match_track(
        self,
        item: Dict[str, Any],
        box: Dict[str, float],
        frame_width: int,
        frame_height: int,
    ) -> DetectionTrack | None:
        label = _label(item)
        category = _category(item)
        best: tuple[float, DetectionTrack] | None = None
        for track in self.tracks.values():
            if track.label != label or track.category != category:
                continue
            stability = self._stability_score(track.box, box, frame_width, frame_height)
            if stability <= 0:
                continue
            if best is None or stability > best[0]:
                best = (stability, track)
        return best[1] if best else None

    def _stability_score(
        self,
        previous: Dict[str, float],
        current: Dict[str, float],
        frame_width: int,
        frame_height: int,
    ) -> float:
        overlap = _iou(previous, current)
        prev_center = _center(previous)
        current_center = _center(current)
        center_shift = (
            ((prev_center[0] - current_center[0]) ** 2 + (prev_center[1] - current_center[1]) ** 2) ** 0.5
            / max(1.0, (frame_width**2 + frame_height**2) ** 0.5)
        )
        prev_area = max(1.0, previous["width"] * previous["height"])
        current_area = max(1.0, current["width"] * current["height"])
        size_change = abs(current_area - prev_area) / max(prev_area, current_area)
        if overlap >= self.config.stability_iou_threshold:
            return overlap
        if center_shift <= self.config.stability_center_shift_ratio and size_change <= self.config.stability_size_change_ratio:
            return 0.01 + (self.config.stability_center_shift_ratio - center_shift)
        return 0.0

    def _new_track(self, item: Dict[str, Any], box: Dict[str, float], now: float) -> DetectionTrack:
        track_id = f"det_{self._next_id}"
        self._next_id += 1
        track = DetectionTrack(track_id=track_id, label=_label(item), category=_category(item), box=box, last_seen=now)
        self.tracks[track_id] = track
        return track

    def _age_tracks(self, seen_tracks: set[str]) -> None:
        for track_id in list(self.tracks):
            if track_id in seen_tracks:
                continue
            track = self.tracks[track_id]
            track.missing_frames += 1
            track.consecutive_frames = 0
            if track.missing_frames > self.config.max_track_missing_frames:
                del self.tracks[track_id]

    def _trim_tracks(self) -> None:
        if len(self.tracks) <= self.config.max_tracks:
            return
        ordered = sorted(self.tracks.values(), key=lambda track: track.last_seen)
        for track in ordered[: len(self.tracks) - self.config.max_tracks]:
            self.tracks.pop(track.track_id, None)

    @staticmethod
    def _enrich(item: Dict[str, Any], track: DetectionTrack) -> Dict[str, Any]:
        enriched = dict(item)
        enriched["track_id"] = track.track_id
        enriched["consecutive_frames"] = track.consecutive_frames
        enriched["confirmed"] = track.confirmed
        return enriched

    def _append_rejected(self, target: list[Dict[str, Any]], item: Dict[str, Any], reason: str) -> None:
        enriched = dict(item)
        enriched["state"] = "rejected"
        enriched["reason"] = reason
        self._log_rejection(enriched, reason.replace("_", " ").title())
        target.append(enriched)

    @staticmethod
    def _log_rejection(item: Dict[str, Any], reason: str) -> None:
        logging.info(
            "Detection rejected: reason=%s label=%s category=%s confidence=%.2f box=%s",
            reason,
            _label(item),
            _category(item),
            _confidence(item),
            item.get("box", {}),
        )


def load_detection_filter_config(path: Path | None) -> DetectionFilterConfig:
    if path is None or not path.exists():
        return DetectionFilterConfig()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logging.warning("Could not read detection filter config from %s: %s", path, exc)
        return DetectionFilterConfig()
    section = data.get("detection_filter", data) if isinstance(data, dict) else {}
    if not isinstance(section, dict):
        logging.warning("Detection filter config must be a JSON object; using defaults.")
        return DetectionFilterConfig()
    return DetectionFilterConfig.from_mapping(section)

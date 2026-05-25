"""
STASIS webcam dataset capture assistant.

Shows a planned shot prompt, waits until the camera view is steady, then saves
the image automatically into dataset/raw/<class_name>/.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np


DEFAULT_CLASSES = [
    "person",
    "animal_stand_in",
    "red_strip",
    "track_mark",
    "fire_card",
    "demo_object",
    "empty_background",
]

SHOT_PLAN = [
    "front view, object centered",
    "front view, object on left side",
    "front view, object on right side",
    "left side angle",
    "right side angle",
    "low rover-height angle",
    "close distance",
    "medium distance",
    "far distance",
    "partly cut off at frame edge",
    "partly hidden behind another object",
    "messy background",
    "clean background",
    "bright lighting",
    "normal lighting",
    "dim lighting or shadow",
    "slightly tilted camera",
    "object near floor",
    "object near wall",
    "mixed scene with harmless objects nearby",
]

EMPTY_BACKGROUND_PLAN = [
    "empty demo area, center view",
    "empty wall and floor",
    "empty area with harmless objects",
    "empty area in bright light",
    "empty area in dim light",
    "empty area from low rover-height angle",
    "empty area with red/orange non-target object",
    "empty area with plants/props but no target",
    "empty area with messy background",
    "empty area from far distance",
]


@dataclass
class CaptureState:
    class_name: str
    prompt_index: int = 0
    saved_count: int = 0
    last_saved_path: Path | None = None
    auto_armed_at: float | None = None
    countdown_started_at: float | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="STASIS guided webcam photo capture tool")
    parser.add_argument("--class-name", choices=DEFAULT_CLASSES, help="Class folder to capture")
    parser.add_argument("--output", type=Path, default=Path("dataset/raw"), help="Output dataset/raw folder")
    parser.add_argument("--camera", type=int, default=0, help="Webcam index")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=int, default=20)
    parser.add_argument("--shots-per-prompt", type=int, default=3, help="Photos to take for each prompt")
    parser.add_argument("--stable-seconds", type=float, default=1.2, help="How long the view must stay still before capture")
    parser.add_argument("--countdown-seconds", type=float, default=1.5, help="Countdown after the view is steady")
    parser.add_argument("--motion-threshold", type=float, default=4.0, help="Lower means stricter stillness detection")
    parser.add_argument("--manual", action="store_true", help="Disable auto capture; press C to capture")
    parser.add_argument("--classes-json", type=Path, help="Optional JSON list of class names")
    return parser.parse_args()


def load_classes(path: Path | None) -> list[str]:
    if path is None:
        return DEFAULT_CLASSES
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not all(isinstance(item, str) and item.strip() for item in data):
        raise SystemExit("classes-json must be a JSON list of class names")
    return [item.strip() for item in data]


def choose_class(classes: list[str]) -> str:
    print("\nSTASIS capture classes:")
    for index, class_name in enumerate(classes, start=1):
        print(f"{index}. {class_name}")
    while True:
        choice = input("Choose class number: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(classes):
            return classes[int(choice) - 1]
        print("Please enter a valid number.")


def prompts_for_class(class_name: str) -> list[str]:
    if class_name == "empty_background":
        return EMPTY_BACKGROUND_PLAN
    return SHOT_PLAN


def create_capture_path(output_root: Path, class_name: str) -> Path:
    folder = output_root / class_name
    folder.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return folder / f"{class_name}_{timestamp}.jpg"


def measure_motion(previous_gray: np.ndarray | None, gray: np.ndarray) -> float:
    if previous_gray is None:
        return 999.0
    diff = cv2.absdiff(previous_gray, gray)
    return float(np.mean(diff))


def put_text_block(frame: np.ndarray, lines: Iterable[str]) -> None:
    x = 16
    y = 28
    line_height = 28
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (frame.shape[1], 150), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.58, frame, 0.42, 0, frame)
    for line in lines:
        cv2.putText(frame, line, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (255, 255, 255), 2)
        y += line_height


def save_frame(frame: np.ndarray, output_root: Path, class_name: str) -> Path:
    path = create_capture_path(output_root, class_name)
    if not cv2.imwrite(str(path), frame):
        raise RuntimeError(f"Could not save {path}")
    return path


def main() -> None:
    args = parse_args()
    classes = load_classes(args.classes_json)
    class_name = args.class_name or choose_class(classes)
    state = CaptureState(class_name=class_name)
    prompts = prompts_for_class(class_name)

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise SystemExit(f"Could not open webcam index {args.camera}")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    cap.set(cv2.CAP_PROP_FPS, args.fps)

    window_name = "STASIS Dataset Capture Assistant"
    previous_gray: np.ndarray | None = None
    prompt_capture_count = 0
    paused = False

    print("\nControls:")
    print("  C = capture now")
    print("  S = skip prompt")
    print("  R = delete last saved image")
    print("  P = pause/resume auto capture")
    print("  Q = quit\n")

    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                print("Camera read failed.")
                time.sleep(0.2)
                continue

            raw_frame = frame.copy()
            prompt = prompts[state.prompt_index % len(prompts)]
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (7, 7), 0)
            motion = measure_motion(previous_gray, gray)
            previous_gray = gray

            now = time.monotonic()
            is_stable = motion <= args.motion_threshold
            if args.manual or paused:
                state.auto_armed_at = None
                state.countdown_started_at = None
            elif is_stable:
                if state.auto_armed_at is None:
                    state.auto_armed_at = now
                if now - state.auto_armed_at >= args.stable_seconds and state.countdown_started_at is None:
                    state.countdown_started_at = now
            else:
                state.auto_armed_at = None
                state.countdown_started_at = None

            countdown_text = ""
            if state.countdown_started_at is not None:
                remaining = args.countdown_seconds - (now - state.countdown_started_at)
                countdown_text = f"Auto capture in {max(0.0, remaining):.1f}s"
                if remaining <= 0:
                    saved = save_frame(raw_frame, args.output, class_name)
                    state.saved_count += 1
                    state.last_saved_path = saved
                    prompt_capture_count += 1
                    print(f"Saved {saved}")
                    state.auto_armed_at = None
                    state.countdown_started_at = None
                    previous_gray = None
                    if prompt_capture_count >= args.shots_per_prompt:
                        prompt_capture_count = 0
                        state.prompt_index += 1

            status = "manual" if args.manual else "paused" if paused else "steady" if is_stable else "move into position"
            put_text_block(
                frame,
                [
                    f"Class: {class_name}    Saved: {state.saved_count}",
                    f"Shot: {prompt}",
                    f"Prompt photo {prompt_capture_count + 1}/{args.shots_per_prompt}    Motion: {motion:.1f}    {status}",
                    countdown_text or "C capture | S skip | R delete last | P pause | Q quit",
                ],
            )
            cv2.imshow(window_name, frame)
            key = cv2.waitKey(1) & 0xFF

            if key in {ord("q"), ord("Q"), 27}:
                break
            if key in {ord("c"), ord("C")}:
                saved = save_frame(raw_frame, args.output, class_name)
                state.saved_count += 1
                state.last_saved_path = saved
                prompt_capture_count += 1
                print(f"Saved {saved}")
                if prompt_capture_count >= args.shots_per_prompt:
                    prompt_capture_count = 0
                    state.prompt_index += 1
            elif key in {ord("s"), ord("S")}:
                prompt_capture_count = 0
                state.prompt_index += 1
                state.auto_armed_at = None
                state.countdown_started_at = None
            elif key in {ord("r"), ord("R")} and state.last_saved_path is not None:
                if state.last_saved_path.exists():
                    state.last_saved_path.unlink()
                    state.saved_count = max(0, state.saved_count - 1)
                    print(f"Deleted {state.last_saved_path}")
                state.last_saved_path = None
            elif key in {ord("p"), ord("P")}:
                paused = not paused
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print(f"Finished. Saved {state.saved_count} images for {class_name}.")


if __name__ == "__main__":
    main()

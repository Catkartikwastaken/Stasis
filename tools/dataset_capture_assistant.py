"""
STASIS guided webcam dataset capture app.

The app stays open while you capture hundreds of photos, shows the next shot
prompt, and saves images to the laptop under Pictures/STASIS_Dataset/raw by
default.
"""

from __future__ import annotations

import argparse
import json
import time
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import cv2
import numpy as np
from PIL import Image, ImageTk


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
    "Front view, object centered",
    "Front view, object on left side",
    "Front view, object on right side",
    "Left side angle",
    "Right side angle",
    "Low rover-height angle",
    "Close distance",
    "Medium distance",
    "Far distance",
    "Partly cut off at frame edge",
    "Partly hidden behind another object",
    "Messy background",
    "Clean background",
    "Bright lighting",
    "Normal lighting",
    "Dim lighting or shadow",
    "Slightly tilted camera",
    "Object near floor",
    "Object near wall",
    "Mixed scene with harmless objects nearby",
]

EMPTY_BACKGROUND_PLAN = [
    "Empty demo area, center view",
    "Empty wall and floor",
    "Empty area with harmless objects",
    "Empty area in bright light",
    "Empty area in dim light",
    "Empty area from low rover-height angle",
    "Empty area with red/orange non-target object",
    "Empty area with plants/props but no target",
    "Empty area with messy background",
    "Empty area from far distance",
]


@dataclass
class CaptureSettings:
    output: Path
    camera: int
    width: int
    height: int
    fps: int
    shots_per_prompt: int
    stable_seconds: float
    countdown_seconds: float
    motion_threshold: float
    manual: bool


def default_output_dir() -> Path:
    return Path.home() / "Pictures" / "STASIS_Dataset" / "raw"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="STASIS guided webcam photo capture app")
    parser.add_argument("--class-name", choices=DEFAULT_CLASSES, default="person")
    parser.add_argument("--output", type=Path, default=default_output_dir())
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=540)
    parser.add_argument("--fps", type=int, default=20)
    parser.add_argument("--shots-per-prompt", type=int, default=5)
    parser.add_argument("--stable-seconds", type=float, default=1.0)
    parser.add_argument("--countdown-seconds", type=float, default=1.2)
    parser.add_argument("--motion-threshold", type=float, default=4.0)
    parser.add_argument("--manual", action="store_true", help="Start with auto capture disabled")
    parser.add_argument("--classes-json", type=Path, help="Optional JSON list of class names")
    return parser.parse_args()


def load_classes(path: Path | None) -> list[str]:
    if path is None:
        return DEFAULT_CLASSES
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not all(isinstance(item, str) and item.strip() for item in data):
        raise SystemExit("classes-json must be a JSON list of class names")
    return [item.strip() for item in data]


def prompts_for_class(class_name: str) -> list[str]:
    return EMPTY_BACKGROUND_PLAN if class_name == "empty_background" else SHOT_PLAN


def create_capture_path(output_root: Path, class_name: str) -> Path:
    folder = output_root / class_name
    folder.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return folder / f"{class_name}_{timestamp}.jpg"


def measure_motion(previous_gray: np.ndarray | None, gray: np.ndarray) -> float:
    if previous_gray is None:
        return 999.0
    return float(np.mean(cv2.absdiff(previous_gray, gray)))


class DatasetCaptureApp:
    def __init__(self, root: tk.Tk, classes: list[str], settings: CaptureSettings, initial_class: str) -> None:
        self.root = root
        self.classes = classes
        self.settings = settings
        self.class_name = tk.StringVar(value=initial_class)
        self.output_dir = tk.StringVar(value=str(settings.output))
        self.prompt_index = 0
        self.prompt_capture_count = 0
        self.saved_total = 0
        self.last_saved_path: Path | None = None
        self.previous_gray: np.ndarray | None = None
        self.current_frame: np.ndarray | None = None
        self.photo_ref: ImageTk.PhotoImage | None = None
        self.auto_enabled = tk.BooleanVar(value=not settings.manual)
        self.paused = False
        self.auto_armed_at: float | None = None
        self.countdown_started_at: float | None = None
        self.motion_value = 999.0

        self.cap = cv2.VideoCapture(settings.camera)
        if not self.cap.isOpened():
            raise SystemExit(f"Could not open webcam index {settings.camera}")
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, settings.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.height)
        self.cap.set(cv2.CAP_PROP_FPS, settings.fps)

        self.root.title("STASIS Dataset Capture")
        self.root.geometry("1180x760")
        self.root.minsize(980, 650)
        self.root.configure(bg="#101714")
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<space>", lambda _event: self.capture_now())
        self.root.bind("<c>", lambda _event: self.capture_now())
        self.root.bind("<s>", lambda _event: self.skip_prompt())
        self.root.bind("<r>", lambda _event: self.delete_last())
        self.root.bind("<p>", lambda _event: self.toggle_auto())

        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("TFrame", background="#101714")
        self.style.configure("Panel.TFrame", background="#18241f")
        self.style.configure("TLabel", background="#101714", foreground="#e7f1ea", font=("Segoe UI", 10))
        self.style.configure("Panel.TLabel", background="#18241f", foreground="#e7f1ea", font=("Segoe UI", 10))
        self.style.configure("Title.TLabel", background="#18241f", foreground="#ffffff", font=("Segoe UI Semibold", 18))
        self.style.configure("Prompt.TLabel", background="#18241f", foreground="#ffcf5a", font=("Segoe UI Semibold", 16))
        self.style.configure("Big.TButton", font=("Segoe UI Semibold", 11), padding=(12, 8))
        self.style.configure("TButton", font=("Segoe UI", 10), padding=(10, 6))
        self.style.configure("TCombobox", padding=(6, 4))

        self.build_ui()
        self.update_prompt_labels()
        self.update_loop()

    def build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=16)
        main.pack(fill="both", expand=True)

        video_panel = ttk.Frame(main, style="Panel.TFrame", padding=12)
        video_panel.pack(side="left", fill="both", expand=True)
        self.video_label = tk.Label(video_panel, bg="#07100c", bd=0)
        self.video_label.pack(fill="both", expand=True)

        side = ttk.Frame(main, style="Panel.TFrame", padding=18, width=340)
        side.pack(side="right", fill="y", padx=(16, 0))
        side.pack_propagate(False)

        ttk.Label(side, text="STASIS Capture", style="Title.TLabel").pack(anchor="w")
        ttk.Label(side, text="Follow the prompt. Hold steady. The app saves and stays open.", style="Panel.TLabel", wraplength=290).pack(anchor="w", pady=(6, 18))

        ttk.Label(side, text="Class", style="Panel.TLabel").pack(anchor="w")
        self.class_box = ttk.Combobox(side, values=self.classes, textvariable=self.class_name, state="readonly")
        self.class_box.pack(fill="x", pady=(4, 14))
        self.class_box.bind("<<ComboboxSelected>>", lambda _event: self.change_class())

        ttk.Label(side, text="Current Prompt", style="Panel.TLabel").pack(anchor="w")
        self.prompt_label = ttk.Label(side, text="", style="Prompt.TLabel", wraplength=290)
        self.prompt_label.pack(anchor="w", fill="x", pady=(4, 12))

        self.prompt_progress = ttk.Label(side, text="", style="Panel.TLabel")
        self.prompt_progress.pack(anchor="w", pady=(0, 14))

        self.status_label = ttk.Label(side, text="", style="Panel.TLabel", wraplength=290)
        self.status_label.pack(anchor="w", fill="x", pady=(0, 14))

        self.capture_button = ttk.Button(side, text="Capture Now", style="Big.TButton", command=self.capture_now)
        self.capture_button.pack(fill="x", pady=(0, 10))
        ttk.Button(side, text="Skip Prompt", command=self.skip_prompt).pack(fill="x", pady=(0, 8))
        ttk.Button(side, text="Delete Last Photo", command=self.delete_last).pack(fill="x", pady=(0, 8))
        ttk.Checkbutton(side, text="Auto capture when steady", variable=self.auto_enabled, command=self.reset_auto_timer).pack(anchor="w", pady=(4, 14))

        ttk.Separator(side).pack(fill="x", pady=12)
        ttk.Label(side, text="Save Location", style="Panel.TLabel").pack(anchor="w")
        self.output_label = ttk.Label(side, textvariable=self.output_dir, style="Panel.TLabel", wraplength=290)
        self.output_label.pack(anchor="w", fill="x", pady=(4, 8))
        ttk.Button(side, text="Choose Folder", command=self.choose_output_dir).pack(fill="x", pady=(0, 14))

        self.saved_label = ttk.Label(side, text="", style="Panel.TLabel", wraplength=290)
        self.saved_label.pack(anchor="w", fill="x", pady=(0, 10))

        ttk.Label(side, text="Keys: Space/C capture, S skip, R delete, P auto, Q/close quit", style="Panel.TLabel", wraplength=290).pack(anchor="w", side="bottom")
        self.root.bind("<q>", lambda _event: self.close())

    def current_prompts(self) -> list[str]:
        return prompts_for_class(self.class_name.get())

    def current_prompt(self) -> str:
        prompts = self.current_prompts()
        return prompts[self.prompt_index % len(prompts)]

    def update_prompt_labels(self) -> None:
        prompts = self.current_prompts()
        self.prompt_label.configure(text=self.current_prompt())
        self.prompt_progress.configure(
            text=f"Prompt {(self.prompt_index % len(prompts)) + 1}/{len(prompts)}  |  Photo {self.prompt_capture_count + 1}/{self.settings.shots_per_prompt}"
        )
        self.saved_label.configure(
            text=f"Saved this session: {self.saved_total}\nLast: {self.last_saved_path.name if self.last_saved_path else 'none yet'}"
        )

    def change_class(self) -> None:
        self.prompt_index = 0
        self.prompt_capture_count = 0
        self.reset_auto_timer()
        self.update_prompt_labels()

    def choose_output_dir(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.output_dir.get(), title="Choose dataset raw folder")
        if selected:
            self.settings.output = Path(selected)
            self.output_dir.set(str(self.settings.output))

    def reset_auto_timer(self) -> None:
        self.auto_armed_at = None
        self.countdown_started_at = None

    def toggle_auto(self) -> None:
        self.auto_enabled.set(not self.auto_enabled.get())
        self.reset_auto_timer()

    def save_current_frame(self) -> None:
        if self.current_frame is None:
            return
        path = create_capture_path(self.settings.output, self.class_name.get())
        if not cv2.imwrite(str(path), self.current_frame):
            messagebox.showerror("Save failed", f"Could not save:\n{path}")
            return
        self.saved_total += 1
        self.last_saved_path = path
        self.prompt_capture_count += 1
        if self.prompt_capture_count >= self.settings.shots_per_prompt:
            self.prompt_capture_count = 0
            self.prompt_index += 1
        self.reset_auto_timer()
        self.previous_gray = None
        self.update_prompt_labels()

    def capture_now(self) -> None:
        self.save_current_frame()

    def skip_prompt(self) -> None:
        self.prompt_capture_count = 0
        self.prompt_index += 1
        self.reset_auto_timer()
        self.update_prompt_labels()

    def delete_last(self) -> None:
        if self.last_saved_path is None:
            return
        if self.last_saved_path.exists():
            self.last_saved_path.unlink()
        self.saved_total = max(0, self.saved_total - 1)
        self.last_saved_path = None
        self.update_prompt_labels()

    def update_auto_capture(self, gray: np.ndarray) -> str:
        self.motion_value = measure_motion(self.previous_gray, gray)
        self.previous_gray = gray
        now = time.monotonic()
        is_stable = self.motion_value <= self.settings.motion_threshold

        if not self.auto_enabled.get():
            self.reset_auto_timer()
            return f"Manual mode | Motion {self.motion_value:.1f}"
        if not is_stable:
            self.reset_auto_timer()
            return f"Move into position | Motion {self.motion_value:.1f}"
        if self.auto_armed_at is None:
            self.auto_armed_at = now
            return f"Hold steady | Motion {self.motion_value:.1f}"
        if now - self.auto_armed_at < self.settings.stable_seconds:
            remaining = self.settings.stable_seconds - (now - self.auto_armed_at)
            return f"Steady, hold {remaining:.1f}s | Motion {self.motion_value:.1f}"
        if self.countdown_started_at is None:
            self.countdown_started_at = now
        remaining = self.settings.countdown_seconds - (now - self.countdown_started_at)
        if remaining <= 0:
            self.save_current_frame()
            return "Saved. Stay in the app for the next shot."
        return f"Auto capture in {remaining:.1f}s"

    def update_loop(self) -> None:
        ok, frame = self.cap.read()
        if ok and frame is not None:
            self.current_frame = frame.copy()
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (7, 7), 0)
            status = self.update_auto_capture(gray)
            self.status_label.configure(text=status)

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(rgb)
            image.thumbnail((780, 620), Image.Resampling.LANCZOS)
            self.photo_ref = ImageTk.PhotoImage(image=image)
            self.video_label.configure(image=self.photo_ref)
        else:
            self.status_label.configure(text="Camera read failed. Check webcam connection.")
        self.root.after(25, self.update_loop)

    def close(self) -> None:
        self.cap.release()
        self.root.destroy()


def main() -> None:
    args = parse_args()
    classes = load_classes(args.classes_json)
    settings = CaptureSettings(
        output=args.output,
        camera=args.camera,
        width=args.width,
        height=args.height,
        fps=args.fps,
        shots_per_prompt=args.shots_per_prompt,
        stable_seconds=args.stable_seconds,
        countdown_seconds=args.countdown_seconds,
        motion_threshold=args.motion_threshold,
        manual=args.manual,
    )
    root = tk.Tk()
    DatasetCaptureApp(root, classes, settings, args.class_name)
    root.mainloop()


if __name__ == "__main__":
    main()

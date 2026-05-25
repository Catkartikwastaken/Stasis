"""
STASIS simple dataset capture app.

Manual-only webcam capture for the current demo dataset:
alpha tester objects, red strips, and empty backgrounds.
"""

from __future__ import annotations

import argparse
import json
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import cv2
from PIL import Image, ImageTk


DEFAULT_CLASSES = [
    "alpha_tester_object",
    "red_strip",
    "empty_background",
]

LOCATION_PLAN = [
    "Location 1 - change object positions and distance",
    "Location 2 - new background and lighting",
    "Location 3 - low rover-height angle",
    "Location 4 - mixed/random demo scene",
]

SHOT_IDEAS = {
    "alpha_tester_object": [
        "Put one or more random demo objects in view",
        "Change object angle and distance",
        "Put objects near the edge of the frame",
        "Partly hide one object",
        "Use a messy background",
        "Use a clean background",
    ],
    "red_strip": [
        "Show the red strip clearly",
        "Place it horizontal, vertical, or diagonal",
        "Put it on the floor or wall",
        "Move it far from the camera",
        "Move it near the camera",
        "Include red/orange distractions nearby",
    ],
    "empty_background": [
        "No target objects in view",
        "Only floor/wall/background",
        "Harmless objects but no red strip",
        "Different lighting",
        "Different camera angle",
        "Messy but empty demo area",
    ],
}


@dataclass
class CaptureSettings:
    output: Path
    camera: int
    width: int
    height: int
    fps: int


def default_output_dir() -> Path:
    return Path.home() / "Pictures" / "STASIS_Dataset" / "raw"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="STASIS simple webcam dataset capture app")
    parser.add_argument("--class-name", choices=DEFAULT_CLASSES, default="alpha_tester_object")
    parser.add_argument("--output", type=Path, default=default_output_dir())
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=540)
    parser.add_argument("--fps", type=int, default=20)
    parser.add_argument("--classes-json", type=Path, help="Optional JSON list of class names")
    return parser.parse_args()


def load_classes(path: Path | None) -> list[str]:
    if path is None:
        return DEFAULT_CLASSES
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not all(isinstance(item, str) and item.strip() for item in data):
        raise SystemExit("classes-json must be a JSON list of class names")
    return [item.strip() for item in data]


def create_capture_path(output_root: Path, class_name: str) -> Path:
    folder = output_root / class_name
    folder.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return folder / f"{class_name}_{timestamp}.jpg"


class DatasetCaptureApp:
    def __init__(self, root: tk.Tk, classes: list[str], settings: CaptureSettings, initial_class: str) -> None:
        self.root = root
        self.classes = classes
        self.settings = settings
        self.class_name = tk.StringVar(value=initial_class)
        self.output_dir = tk.StringVar(value=str(settings.output))
        self.location_index = 0
        self.idea_index = 0
        self.saved_total = 0
        self.class_counts = {class_name: 0 for class_name in classes}
        self.last_saved_path: Path | None = None
        self.current_frame = None
        self.photo_ref: ImageTk.PhotoImage | None = None
        self.camera_index = tk.IntVar(value=settings.camera)
        self.width_var = tk.IntVar(value=settings.width)
        self.height_var = tk.IntVar(value=settings.height)
        self.fps_var = tk.IntVar(value=settings.fps)
        self.brightness_var = tk.DoubleVar(value=0)
        self.contrast_var = tk.DoubleVar(value=0)
        self.exposure_var = tk.DoubleVar(value=0)
        self.focus_var = tk.DoubleVar(value=0)
        self.camera_info = tk.StringVar(value="Camera info loading...")

        self.cap = cv2.VideoCapture(settings.camera)
        if not self.cap.isOpened():
            raise SystemExit(f"Could not open webcam index {settings.camera}")
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, settings.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.height)
        self.cap.set(cv2.CAP_PROP_FPS, settings.fps)

        self.root.title("STASIS Dataset Capture")
        self.root.geometry("1160x740")
        self.root.minsize(960, 640)
        self.root.configure(bg="#101714")
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<space>", lambda _event: self.capture_now())
        self.root.bind("<c>", lambda _event: self.capture_now())
        self.root.bind("<n>", lambda _event: self.next_idea())
        self.root.bind("<l>", lambda _event: self.next_location())
        self.root.bind("<r>", lambda _event: self.delete_last())
        self.root.bind("<q>", lambda _event: self.close())

        self.setup_style()
        self.build_ui()
        self.refresh_text()
        self.update_loop()

    def setup_style(self) -> None:
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("TFrame", background="#101714")
        self.style.configure("Panel.TFrame", background="#18241f")
        self.style.configure("TLabel", background="#101714", foreground="#e7f1ea", font=("Segoe UI", 10))
        self.style.configure("Panel.TLabel", background="#18241f", foreground="#e7f1ea", font=("Segoe UI", 10))
        self.style.configure("Title.TLabel", background="#18241f", foreground="#ffffff", font=("Segoe UI Semibold", 18))
        self.style.configure("Prompt.TLabel", background="#18241f", foreground="#ffcf5a", font=("Segoe UI Semibold", 15))
        self.style.configure("Big.TButton", font=("Segoe UI Semibold", 12), padding=(14, 10))
        self.style.configure("TButton", font=("Segoe UI", 10), padding=(10, 7))
        self.style.configure("TCombobox", padding=(6, 4))

    def build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=16)
        main.pack(fill="both", expand=True)

        video_panel = ttk.Frame(main, style="Panel.TFrame", padding=12)
        video_panel.pack(side="left", fill="both", expand=True)
        self.video_label = tk.Label(video_panel, bg="#07100c", bd=0)
        self.video_label.pack(fill="both", expand=True)

        side = ttk.Frame(main, style="Panel.TFrame", padding=18, width=350)
        side.pack(side="right", fill="y", padx=(16, 0))
        side.pack_propagate(False)

        ttk.Label(side, text="STASIS Dataset", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            side,
            text="Manual capture only. Pick the class, frame the scene, press Capture. The app stays open.",
            style="Panel.TLabel",
            wraplength=300,
        ).pack(anchor="w", pady=(6, 18))

        ttk.Label(side, text="Current Class", style="Panel.TLabel").pack(anchor="w")
        self.class_box = ttk.Combobox(side, values=self.classes, textvariable=self.class_name, state="readonly")
        self.class_box.pack(fill="x", pady=(4, 14))
        self.class_box.bind("<<ComboboxSelected>>", lambda _event: self.refresh_text())

        self.location_label = ttk.Label(side, text="", style="Panel.TLabel", wraplength=300)
        self.location_label.pack(anchor="w", fill="x", pady=(0, 10))

        ttk.Label(side, text="Photo Idea", style="Panel.TLabel").pack(anchor="w")
        self.idea_label = ttk.Label(side, text="", style="Prompt.TLabel", wraplength=300)
        self.idea_label.pack(anchor="w", fill="x", pady=(4, 16))

        self.capture_button = ttk.Button(side, text="Capture Photo", style="Big.TButton", command=self.capture_now)
        self.capture_button.pack(fill="x", pady=(0, 10))
        ttk.Button(side, text="Next Idea", command=self.next_idea).pack(fill="x", pady=(0, 8))
        ttk.Button(side, text="Next Location", command=self.next_location).pack(fill="x", pady=(0, 8))
        ttk.Button(side, text="Delete Last Photo", command=self.delete_last).pack(fill="x", pady=(0, 14))

        ttk.Separator(side).pack(fill="x", pady=12)
        ttk.Label(side, text="Camera Settings", style="Panel.TLabel").pack(anchor="w")
        camera_grid = ttk.Frame(side, style="Panel.TFrame")
        camera_grid.pack(fill="x", pady=(6, 10))

        ttk.Label(camera_grid, text="Camera", style="Panel.TLabel").grid(row=0, column=0, sticky="w", pady=3)
        ttk.Spinbox(camera_grid, from_=0, to=5, textvariable=self.camera_index, width=8).grid(row=0, column=1, sticky="ew", pady=3)
        ttk.Label(camera_grid, text="Width", style="Panel.TLabel").grid(row=1, column=0, sticky="w", pady=3)
        ttk.Spinbox(camera_grid, from_=320, to=1920, increment=80, textvariable=self.width_var, width=8).grid(row=1, column=1, sticky="ew", pady=3)
        ttk.Label(camera_grid, text="Height", style="Panel.TLabel").grid(row=2, column=0, sticky="w", pady=3)
        ttk.Spinbox(camera_grid, from_=240, to=1080, increment=60, textvariable=self.height_var, width=8).grid(row=2, column=1, sticky="ew", pady=3)
        ttk.Label(camera_grid, text="FPS", style="Panel.TLabel").grid(row=3, column=0, sticky="w", pady=3)
        ttk.Spinbox(camera_grid, from_=5, to=60, increment=5, textvariable=self.fps_var, width=8).grid(row=3, column=1, sticky="ew", pady=3)
        camera_grid.columnconfigure(1, weight=1)

        ttk.Button(side, text="Apply Camera Settings", command=self.apply_camera_settings).pack(fill="x", pady=(0, 8))
        ttk.Button(side, text="Refresh Camera Info", command=self.refresh_camera_info).pack(fill="x", pady=(0, 10))

        self.add_camera_slider(side, "Brightness", self.brightness_var, cv2.CAP_PROP_BRIGHTNESS, -100, 100)
        self.add_camera_slider(side, "Contrast", self.contrast_var, cv2.CAP_PROP_CONTRAST, -100, 100)
        self.add_camera_slider(side, "Exposure", self.exposure_var, cv2.CAP_PROP_EXPOSURE, -13, 1)
        self.add_camera_slider(side, "Focus", self.focus_var, cv2.CAP_PROP_FOCUS, 0, 255)

        ttk.Label(side, textvariable=self.camera_info, style="Panel.TLabel", wraplength=300).pack(anchor="w", fill="x", pady=(4, 10))

        ttk.Separator(side).pack(fill="x", pady=12)
        ttk.Label(side, text="Save Location", style="Panel.TLabel").pack(anchor="w")
        self.output_label = ttk.Label(side, textvariable=self.output_dir, style="Panel.TLabel", wraplength=300)
        self.output_label.pack(anchor="w", fill="x", pady=(4, 8))
        ttk.Button(side, text="Choose Folder", command=self.choose_output_dir).pack(fill="x", pady=(0, 14))

        self.saved_label = ttk.Label(side, text="", style="Panel.TLabel", wraplength=300)
        self.saved_label.pack(anchor="w", fill="x")

        ttk.Label(
            side,
            text="Keys: Space/C capture, N next idea, L next location, R delete, Q quit",
            style="Panel.TLabel",
            wraplength=300,
        ).pack(anchor="w", side="bottom")
        self.refresh_camera_info()

    def add_camera_slider(self, parent: ttk.Frame, label: str, variable: tk.DoubleVar, prop: int, minimum: float, maximum: float) -> None:
        row = ttk.Frame(parent, style="Panel.TFrame")
        row.pack(fill="x", pady=(2, 4))
        ttk.Label(row, text=label, style="Panel.TLabel", width=10).pack(side="left")
        slider = ttk.Scale(row, from_=minimum, to=maximum, variable=variable, command=lambda _value, camera_prop=prop, var=variable: self.set_camera_prop(camera_prop, var.get()))
        slider.pack(side="left", fill="x", expand=True, padx=(8, 0))

    def set_camera_prop(self, prop: int, value: float) -> None:
        if self.cap is not None and self.cap.isOpened():
            self.cap.set(prop, float(value))

    def current_ideas(self) -> list[str]:
        return SHOT_IDEAS.get(self.class_name.get(), SHOT_IDEAS["alpha_tester_object"])

    def refresh_text(self) -> None:
        ideas = self.current_ideas()
        location = LOCATION_PLAN[self.location_index % len(LOCATION_PLAN)]
        idea = ideas[self.idea_index % len(ideas)]
        self.location_label.configure(text=f"Location: {location}")
        self.idea_label.configure(text=idea)
        counts = "\n".join(f"{name}: {self.class_counts.get(name, 0)}" for name in self.classes)
        self.saved_label.configure(
            text=f"Saved this session: {self.saved_total}\n{counts}\nLast: {self.last_saved_path.name if self.last_saved_path else 'none yet'}"
        )

    def choose_output_dir(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.output_dir.get(), title="Choose dataset raw folder")
        if selected:
            self.settings.output = Path(selected)
            self.output_dir.set(str(self.settings.output))

    def apply_camera_settings(self) -> None:
        self.settings.camera = int(self.camera_index.get())
        self.settings.width = int(self.width_var.get())
        self.settings.height = int(self.height_var.get())
        self.settings.fps = int(self.fps_var.get())
        self.cap.release()
        self.cap = cv2.VideoCapture(self.settings.camera)
        if not self.cap.isOpened():
            messagebox.showerror("Camera error", f"Could not open webcam index {self.settings.camera}")
            return
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.settings.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.settings.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.settings.fps)
        self.refresh_camera_info()

    def refresh_camera_info(self) -> None:
        if self.cap is None or not self.cap.isOpened():
            self.camera_info.set("Camera unavailable.")
            return
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        fps = self.cap.get(cv2.CAP_PROP_FPS) or 0
        megapixels = (width * height) / 1_000_000 if width and height else 0
        backend = "unknown"
        try:
            backend = self.cap.getBackendName()
        except Exception:
            pass
        brightness = self.cap.get(cv2.CAP_PROP_BRIGHTNESS)
        contrast = self.cap.get(cv2.CAP_PROP_CONTRAST)
        exposure = self.cap.get(cv2.CAP_PROP_EXPOSURE)
        focus = self.cap.get(cv2.CAP_PROP_FOCUS)
        self.brightness_var.set(brightness if brightness != -1 else 0)
        self.contrast_var.set(contrast if contrast != -1 else 0)
        self.exposure_var.set(exposure if exposure != -1 else 0)
        self.focus_var.set(focus if focus != -1 else 0)
        self.camera_info.set(
            f"Camera {self.settings.camera}: {width}x{height} at {fps:.1f} FPS\n"
            f"Resolution: {megapixels:.2f} MP | Backend: {backend}\n"
            "Power draw: not reported by this webcam/driver\n"
            f"Brightness {brightness:.1f} | Contrast {contrast:.1f} | Exposure {exposure:.1f} | Focus {focus:.1f}"
        )

    def capture_now(self) -> None:
        if self.current_frame is None:
            return
        class_name = self.class_name.get()
        path = create_capture_path(self.settings.output, class_name)
        if not cv2.imwrite(str(path), self.current_frame):
            messagebox.showerror("Save failed", f"Could not save:\n{path}")
            return
        self.saved_total += 1
        self.class_counts[class_name] = self.class_counts.get(class_name, 0) + 1
        self.last_saved_path = path
        self.idea_index += 1
        self.refresh_text()

    def next_idea(self) -> None:
        self.idea_index += 1
        self.refresh_text()

    def next_location(self) -> None:
        self.location_index += 1
        self.idea_index = 0
        self.refresh_text()

    def delete_last(self) -> None:
        if self.last_saved_path is None:
            return
        last_class = self.last_saved_path.parent.name
        if self.last_saved_path.exists():
            self.last_saved_path.unlink()
        self.saved_total = max(0, self.saved_total - 1)
        self.class_counts[last_class] = max(0, self.class_counts.get(last_class, 0) - 1)
        self.last_saved_path = None
        self.refresh_text()

    def update_loop(self) -> None:
        ok, frame = self.cap.read()
        if ok and frame is not None:
            self.current_frame = frame.copy()
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(rgb)
            image.thumbnail((780, 620), Image.Resampling.LANCZOS)
            self.photo_ref = ImageTk.PhotoImage(image=image)
            self.video_label.configure(image=self.photo_ref)
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
    )
    root = tk.Tk()
    DatasetCaptureApp(root, classes, settings, args.class_name)
    root.mainloop()


if __name__ == "__main__":
    main()

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

        self.root.title("STASIS Dataset Studio")
        self.root.geometry("1160x740")
        self.root.minsize(960, 640)
        self.root.configure(bg="#0e1014")
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
        self.style.configure("TFrame", background="#0e1014")
        self.style.configure("Panel.TFrame", background="#171b22")
        self.style.configure("Card.TFrame", background="#202630", relief="flat")
        self.style.configure("TLabel", background="#0e1014", foreground="#f4f7fb", font=("Segoe UI", 10))
        self.style.configure("Panel.TLabel", background="#171b22", foreground="#f4f7fb", font=("Segoe UI", 10))
        self.style.configure("Muted.TLabel", background="#171b22", foreground="#a8b3c5", font=("Segoe UI", 9))
        self.style.configure("Card.TLabel", background="#202630", foreground="#f4f7fb", font=("Segoe UI", 10))
        self.style.configure("Section.TLabel", background="#171b22", foreground="#45e0d2", font=("Segoe UI Semibold", 10))
        self.style.configure("Title.TLabel", background="#171b22", foreground="#ffffff", font=("Segoe UI Semibold", 20))
        self.style.configure("Prompt.TLabel", background="#202630", foreground="#f4c95d", font=("Segoe UI Semibold", 15))
        self.style.configure("Hero.TLabel", background="#171b22", foreground="#ffffff", font=("Segoe UI Semibold", 16))
        self.style.configure("Big.TButton", font=("Segoe UI Semibold", 12), padding=(14, 11), background="#2d6cdf", foreground="#ffffff")
        self.style.map("Big.TButton", background=[("active", "#3d7ff0")])
        self.style.configure("TButton", font=("Segoe UI", 10), padding=(10, 7), background="#263241", foreground="#f4f7fb")
        self.style.configure("TCombobox", padding=(6, 4))
        self.style.configure("Vertical.TScrollbar", background="#263241", troughcolor="#0e1014", arrowcolor="#f4f7fb")

    def build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=18)
        main.pack(fill="both", expand=True)

        video_panel = ttk.Frame(main, style="Panel.TFrame", padding=12)
        video_panel.pack(side="left", fill="both", expand=True)
        video_header = ttk.Frame(video_panel, style="Panel.TFrame")
        video_header.pack(fill="x", pady=(0, 10))
        ttk.Label(video_header, text="Live Webcam", style="Hero.TLabel").pack(side="left")
        ttk.Label(video_header, text="Frame the scene, then capture manually", style="Muted.TLabel").pack(side="right")
        self.video_label = tk.Label(video_panel, bg="#080a0f", bd=0)
        self.video_label.pack(fill="both", expand=True)

        side_shell = ttk.Frame(main, style="Panel.TFrame", width=390)
        side_shell.pack(side="right", fill="y", padx=(16, 0))
        side_shell.pack_propagate(False)

        side_canvas = tk.Canvas(side_shell, bg="#171b22", highlightthickness=0, bd=0)
        side_scrollbar = ttk.Scrollbar(side_shell, orient="vertical", command=side_canvas.yview)
        side_canvas.configure(yscrollcommand=side_scrollbar.set)
        side_scrollbar.pack(side="right", fill="y")
        side_canvas.pack(side="left", fill="both", expand=True)

        side = ttk.Frame(side_canvas, style="Panel.TFrame", padding=18)
        side_window = side_canvas.create_window((0, 0), window=side, anchor="nw")

        def resize_side(event: tk.Event) -> None:
            side_canvas.itemconfigure(side_window, width=event.width)

        def refresh_scroll_region(_event: tk.Event | None = None) -> None:
            side_canvas.configure(scrollregion=side_canvas.bbox("all"))

        side_canvas.bind("<Configure>", resize_side)
        side.bind("<Configure>", refresh_scroll_region)
        side_canvas.bind_all("<MouseWheel>", lambda event: side_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units"))

        ttk.Label(side, text="STASIS Dataset Studio", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            side,
            text="Manual capture only. Pick a class, frame the scene, and save clean training photos.",
            style="Muted.TLabel",
            wraplength=330,
        ).pack(anchor="w", pady=(6, 18))

        ttk.Label(side, text="Dataset", style="Section.TLabel").pack(anchor="w", pady=(0, 6))
        dataset_card = ttk.Frame(side, style="Card.TFrame", padding=12)
        dataset_card.pack(fill="x", pady=(0, 14))

        ttk.Label(dataset_card, text="Current Class", style="Card.TLabel").pack(anchor="w")
        self.class_box = ttk.Combobox(side, values=self.classes, textvariable=self.class_name, state="readonly")
        self.class_box.pack(in_=dataset_card, fill="x", pady=(4, 12))
        self.class_box.bind("<<ComboboxSelected>>", lambda _event: self.refresh_text())

        self.location_label = ttk.Label(dataset_card, text="", style="Card.TLabel", wraplength=310)
        self.location_label.pack(anchor="w", fill="x", pady=(0, 10))

        ttk.Label(dataset_card, text="Photo Idea", style="Card.TLabel").pack(anchor="w")
        self.idea_label = ttk.Label(dataset_card, text="", style="Prompt.TLabel", wraplength=310)
        self.idea_label.pack(anchor="w", fill="x", pady=(4, 4))

        self.capture_button = ttk.Button(side, text="Save Frame", style="Big.TButton", command=self.capture_now)
        self.capture_button.pack(fill="x", pady=(0, 10))
        ttk.Button(side, text="Next Idea", command=self.next_idea).pack(fill="x", pady=(0, 8))
        ttk.Button(side, text="Next Location", command=self.next_location).pack(fill="x", pady=(0, 8))
        ttk.Button(side, text="Delete Last Photo", command=self.delete_last).pack(fill="x", pady=(0, 14))

        ttk.Label(side, text="Camera", style="Section.TLabel").pack(anchor="w", pady=(10, 6))
        camera_card = ttk.Frame(side, style="Card.TFrame", padding=12)
        camera_card.pack(fill="x", pady=(0, 14))
        camera_grid = ttk.Frame(camera_card, style="Card.TFrame")
        camera_grid.pack(fill="x", pady=(0, 10))

        ttk.Label(camera_grid, text="Camera", style="Card.TLabel").grid(row=0, column=0, sticky="w", pady=3)
        ttk.Spinbox(camera_grid, from_=0, to=5, textvariable=self.camera_index, width=8).grid(row=0, column=1, sticky="ew", pady=3)
        ttk.Label(camera_grid, text="Width", style="Card.TLabel").grid(row=1, column=0, sticky="w", pady=3)
        ttk.Spinbox(camera_grid, from_=320, to=1920, increment=80, textvariable=self.width_var, width=8).grid(row=1, column=1, sticky="ew", pady=3)
        ttk.Label(camera_grid, text="Height", style="Card.TLabel").grid(row=2, column=0, sticky="w", pady=3)
        ttk.Spinbox(camera_grid, from_=240, to=1080, increment=60, textvariable=self.height_var, width=8).grid(row=2, column=1, sticky="ew", pady=3)
        ttk.Label(camera_grid, text="FPS", style="Card.TLabel").grid(row=3, column=0, sticky="w", pady=3)
        ttk.Spinbox(camera_grid, from_=5, to=60, increment=5, textvariable=self.fps_var, width=8).grid(row=3, column=1, sticky="ew", pady=3)
        camera_grid.columnconfigure(1, weight=1)

        ttk.Button(camera_card, text="Apply Camera Settings", command=self.apply_camera_settings).pack(fill="x", pady=(0, 8))
        ttk.Button(camera_card, text="Refresh Camera Info", command=self.refresh_camera_info).pack(fill="x", pady=(0, 10))

        self.add_camera_slider(camera_card, "Brightness", self.brightness_var, cv2.CAP_PROP_BRIGHTNESS, -100, 100)
        self.add_camera_slider(camera_card, "Contrast", self.contrast_var, cv2.CAP_PROP_CONTRAST, -100, 100)
        self.add_camera_slider(camera_card, "Exposure", self.exposure_var, cv2.CAP_PROP_EXPOSURE, -13, 1)
        self.add_camera_slider(camera_card, "Focus", self.focus_var, cv2.CAP_PROP_FOCUS, 0, 255)

        ttk.Label(camera_card, textvariable=self.camera_info, style="Card.TLabel", wraplength=310).pack(anchor="w", fill="x", pady=(4, 0))

        ttk.Label(side, text="Storage", style="Section.TLabel").pack(anchor="w", pady=(4, 6))
        storage_card = ttk.Frame(side, style="Card.TFrame", padding=12)
        storage_card.pack(fill="x", pady=(0, 14))
        ttk.Label(storage_card, text="Save Location", style="Card.TLabel").pack(anchor="w")
        self.output_label = ttk.Label(storage_card, textvariable=self.output_dir, style="Card.TLabel", wraplength=310)
        self.output_label.pack(anchor="w", fill="x", pady=(4, 8))
        ttk.Button(storage_card, text="Choose Folder", command=self.choose_output_dir).pack(fill="x")

        self.saved_label = ttk.Label(side, text="", style="Panel.TLabel", wraplength=330)
        self.saved_label.pack(anchor="w", fill="x")

        ttk.Label(
            side,
            text="Keys: Space/C capture, N next idea, L next location, R delete, Q quit",
            style="Muted.TLabel",
            wraplength=330,
        ).pack(anchor="w", pady=(18, 0))
        self.refresh_camera_info()

    def add_camera_slider(self, parent: ttk.Frame, label: str, variable: tk.DoubleVar, prop: int, minimum: float, maximum: float) -> None:
        row = ttk.Frame(parent, style="Card.TFrame")
        row.pack(fill="x", pady=(4, 5))
        ttk.Label(row, text=label, style="Card.TLabel", width=10).pack(side="left")
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

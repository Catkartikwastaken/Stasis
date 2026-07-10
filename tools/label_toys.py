"""
STASIS Toy Labeling Tool
========================
Lets you draw multiple bounding boxes per photo — one per toy.
Click and drag to draw a box, each one stays visible as you add more.

Usage:
    python tools/label_toys.py

Controls:
    - Click & drag : draw a box around a toy (repeat for multiple)
    - SPACE / ENTER: finish this image, save all boxes, move to next
    - R           : reset all boxes for current image (start over)
    - ESC         : skip this image (keep existing boxes if any)
    - Q           : quit early (saves progress)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np


# ── Mouse callback state ──────────────────────────────────────────
class BoxDrawer:
    def __init__(self, img: np.ndarray, scale: float, window: str):
        self.base = img.copy()
        self.canvas = img.copy()
        self.scale = scale
        self.window = window
        self.boxes: list[tuple[int, int, int, int]] = []  # display-coord (x1,y1,x2,y2)
        self.drawing = False
        self.ix = self.iy = -1

    def redraw(self):
        self.canvas = self.base.copy()
        for i, (x1, y1, x2, y2) in enumerate(self.boxes):
            color = (50, 220, 50) if i % 2 == 0 else (50, 200, 255)
            cv2.rectangle(self.canvas, (x1, y1), (x2, y2), color, 3)
            lbl = f"#{i + 1}"
            (tw, th), _ = cv2.getTextSize(lbl, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(self.canvas, (x1, y1 - th - 8), (x1 + tw + 8, y1), color, -1)
            cv2.putText(self.canvas, lbl, (x1 + 4, y1 - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (10, 10, 10), 2)
        cv2.imshow(self.window, self.canvas)

    def mouse(self, event: int, x: int, y: int, flags: int, _param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.drawing = True
            self.ix, self.iy = x, y
        elif event == cv2.EVENT_MOUSEMOVE and self.drawing:
            tmp = self.canvas.copy()
            for bx1, by1, bx2, by2 in self.boxes:
                cv2.rectangle(tmp, (bx1, by1), (bx2, by2), (50, 220, 50), 3)
            cv2.rectangle(tmp, (self.ix, self.iy), (x, y), (50, 180, 255), 2)
            cv2.imshow(self.window, tmp)
        elif event == cv2.EVENT_LBUTTONUP:
            self.drawing = False
            x1, y1 = min(self.ix, x), min(self.iy, y)
            x2, y2 = max(self.ix, x), max(self.iy, y)
            if (x2 - x1) > 10 and (y2 - y1) > 10:
                self.boxes.append((x1, y1, x2, y2))
            self.redraw()


def label_image(img: np.ndarray, fname: str, scale: float) -> list[dict] | None:
    """Show image, let user draw boxes. Return list of boxes or None to skip."""
    h, w = img.shape[:2]
    win = "STASIS Labeler — drag box(es) | SPACE=done | R=reset | ESC=skip | Q=quit"
    dh, dw = int(h * scale), int(w * scale)

    # Info bar
    info = np.zeros((48, dw, 3), dtype=np.uint8)
    cv2.putText(info, "Drag around each toy | SPACE=done | R=reset | ESC=skip | Q=quit",
                (10, 31), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (200, 200, 200), 1)

    display = cv2.resize(img, (dw, dh))
    canvas = np.vstack([info, display])

    drawer = BoxDrawer(canvas, scale, win)

    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win, min(dw, 1400), min(dh + 48 + 30, 900))
    drawer.redraw()
    cv2.setMouseCallback(win, drawer.mouse)

    print(f"\n  [LABEL] {fname} ({w}x{h})")
    print("          Draw boxes around each toy, then press SPACE when done.")

    while True:
        key = cv2.waitKey(0) & 0xFF

        if key == ord(" ") or key == 13:  # SPACE / ENTER → done with this image
            break

        if key == ord("r") or key == ord("R"):  # Reset
            drawer.boxes.clear()
            drawer.redraw()
            print("          [RESET] All boxes cleared for this image")
            continue

        if key == 27:  # ESC → skip
            cv2.destroyWindow(win)
            return None  # skip

        if key == ord("q") or key == ord("Q"):  # Quit
            cv2.destroyWindow(win)
            return "QUIT"

    cv2.destroyWindow(win)

    return drawer.boxes  # list of (x1,y1,x2,y2) in display coords


def scale_box(box: tuple[int, int, int, int], scale: float) -> dict:
    """Convert display-coord box to original image coord dict."""
    x1, y1, x2, y2 = box
    return {
        "x": int(x1 / scale),
        "y": int(y1 / scale),
        "width": int((x2 - x1) / scale),
        "height": int((y2 - y1) / scale),
    }


def main() -> int:
    animals_dir = Path(r"C:\Users\Car\Stasis\Animals")
    labels_path = animals_dir / "toy_labels.json"

    # ── Find images ───────────────────────────────────────────────
    exts = {".jpg", ".jpeg", ".png", ".bmp"}
    images = sorted(
        p for p in animals_dir.iterdir()
        if p.suffix.lower() in exts and not p.name.startswith("label_")
    )
    if not images:
        print(f"[ERROR] No images found in {animals_dir}/")
        return 1

    print(f"Found {len(images)} image(s)")
    print()

    # ── Load existing labels (new format: list per image) ─────────
    existing: dict[str, list[dict]] = {}
    if labels_path.exists():
        try:
            raw = json.loads(labels_path.read_text("utf-8"))
            # Normalise: old format was {fname: dict}, new is {fname: [dict, ...]}
            for k, v in raw.items():
                if isinstance(v, dict):
                    existing[k] = [v]
                elif isinstance(v, list):
                    existing[k] = v
            print(f"Loaded {sum(len(v) for v in existing.values())} existing box(es)")
            print("Already-labeled images will be SKIPPED.")
        except Exception as exc:
            print(f"Warning: Could not load existing labels: {exc}")
    print()

    # ── Process each image ────────────────────────────────────────
    labels: dict[str, list[dict]] = {k: list(v) for k, v in existing.items()}
    max_dim = 1200

    for img_path in images:
        fname = img_path.name
        if fname in labels:
            count = len(labels[fname])
            print(f"  [SKIP]  {fname} — {count} box(es) already labeled")
            continue

        img = cv2.imread(str(img_path))
        if img is None:
            print(f"  [ERR]   {fname} — could not read")
            continue

        h, w = img.shape[:2]
        scale = min(max_dim / w, max_dim / h, 1.0)

        result = label_image(img, fname, scale)

        if result is None:
            # ESC → skip, no boxes saved
            print("          [SKIP]")
            labels[fname] = []
            continue

        if result == "QUIT":
            print("          [QUIT] Saving progress...")
            break

        # Convert display coords to original coords
        boxes_orig = [scale_box(b, scale) for b in result]
        total_area = sum(b["width"] * b["height"] for b in boxes_orig)
        frame_area = w * h
        labels[fname] = boxes_orig
        print(f"          [OK]    {len(boxes_orig)} box(es), "
              f"{total_area / frame_area * 100:.1f}% of frame total")

    # ── Save ──────────────────────────────────────────────────────
    labels_path.write_text(json.dumps(labels, indent=2, sort_keys=True), "utf-8")
    print(f"\n{'=' * 60}")
    print(f"Saved to {labels_path} — {sum(len(v) for v in labels.values())} total box(es)")
    print(f"Labeled images: {sum(1 for v in labels.values() if v)}/{len(images)}")
    if labels:
        print(f"\nNext: python tools/generate_vpe_from_labels.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())

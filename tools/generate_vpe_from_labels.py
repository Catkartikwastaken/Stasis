"""
Generate VPE from manual toy labels
====================================
After running label_toys.py and drawing boxes around each toy,
run this script to:
  1. Crop reference images to the labeled boxes
  2. Regenerate the VPE embeddings
  3. Test the detection

Usage:
    python tools/generate_vpe_from_labels.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np


def main() -> int:
    server_dir = Path(r"C:\Users\Car\Stasis\server")
    animals_dir = Path(r"C:\Users\Car\Stasis\Animals")
    ref_dir = server_dir / "reference"
    labels_path = animals_dir / "toy_labels.json"
    output_vpe = server_dir / "models" / "toy_embeddings.pt"

    # --- Check labels exist ---
    if not labels_path.exists():
        print(f"[ERROR] Labels file not found: {labels_path}")
        print("Run label_toys.py first to label your images.")
        return 1

    labels = json.loads(labels_path.read_text(encoding="utf-8"))
    if not labels:
        print("[ERROR] Labels file is empty. Run label_toys.py to label images.")
        return 1

    # Normalise to list-of-boxes format
    for k, v in list(labels.items()):
        if isinstance(v, dict):
            labels[k] = [v]

    total_boxes = sum(len(v) for v in labels.values())
    print(f"Loaded {total_boxes} box(es) across {len(labels)} image(s)")
    print()

    # --- Backup old reference ---
    backup_dir = server_dir / "reference_backup_manual"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for f in ref_dir.glob("toy_*.jpg"):
        shutil.copy2(f, backup_dir / f.name)
    print(f"Backed up old reference images to {backup_dir}/")

    # --- Clear reference dir ---
    for f in ref_dir.glob("*.jpg"):
        f.unlink()
    print("Cleared reference directory")

    # --- Crop each labeled box → one reference image per box ---
    crop_info = []
    idx = 0
    for fname, boxes in sorted(labels.items()):
        src = animals_dir / fname
        if not src.exists():
            print(f"  [SKIP] {fname} — file not found")
            continue

        img = cv2.imread(str(src))
        if img is None:
            print(f"  [SKIP] {fname} — could not read")
            continue

        h, w = img.shape[:2]
        for box in boxes:
            idx += 1
            x = int(box["x"])
            y = int(box["y"])
            bw = int(box["width"])
            bh = int(box["height"])

            # Add 15% margin around the box for context
            margin_x = int(bw * 0.15)
            margin_y = int(bh * 0.15)
            x1 = max(0, x - margin_x)
            y1 = max(0, y - margin_y)
            x2 = min(w, x + bw + margin_x)
            y2 = min(h, y + bh + margin_y)

            crop = img[y1:y2, x1:x2]
            out_name = f"toy_{idx}.jpg"
            out_path = ref_dir / out_name
            cv2.imwrite(str(out_path), crop)

            ch, cw = crop.shape[:2]
            obj_pct = (bw * bh) / (w * h) * 100
            print(f"  {fname} -> {out_name}: crop=({x1},{y1},{x2},{y2}) = {cw}x{ch} ({obj_pct:.1f}% frame)")
            crop_info.append((fname, out_name, x1, y1, x2, y2))

    print(f"\nCreated {idx} cropped reference images from {total_boxes} box(es)")
    print()

    # --- Generate VPE ---
    print("=" * 60)
    print("Generating VPE embeddings...")
    print("=" * 60)

    venv_python = str(server_dir / ".venv" / "Scripts" / "python.exe")
    script = str(server_dir / "generate_toy_embeddings.py")

    cmd = [
        venv_python,
        script,
        "--reference-dir", str(ref_dir),
        "--output", str(output_vpe),
        "--device", "cuda:0",
        "--crop", "0.0",
    ]

    print(f"Running: {' '.join(cmd)}")
    print()

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr[:1000])
    print(f"Exit code: {result.returncode}")

    if result.returncode != 0:
        print("[ERROR] VPE generation failed!")
        return 1

    # --- Quick verification ---
    print("=" * 60)
    print("Quick verification...")
    print("=" * 60)

    import torch
    from ultralytics import YOLOE

    model = YOLOE(str(server_dir / "yoloe-26s-seg.pt")).to("cuda:0")
    saved = torch.load(str(output_vpe), map_location="cuda:0", weights_only=False)
    model.model.set_classes(saved["combined_names"], saved["combined_pe"].to("cuda:0"))

    print(f"VPE classes: {saved['combined_names']}")

    # Test on the crops themselves
    for fname in sorted(ref_dir.glob("toy_*.jpg")):
        test_img = cv2.imread(str(fname))
        if test_img is None:
            continue
        results = model.predict(source=test_img, imgsz=640, conf=0.01, device="cuda:0", verbose=False)
        if results[0].boxes is not None:
            for box in results[0].boxes:
                cid = int(box.cls[0])
                label = results[0].names.get(cid, cid)
                conf = float(box.conf[0])
                if conf > 0.01 and label == "wildlife":
                    x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
                    fw, fh = test_img.shape[1], test_img.shape[0]
                    print(f"  {fname.name}: wildlife conf={conf:.3f} box=({x1},{y1},{x2},{y2}) "
                          f"(frame={fw}x{fh})")

    print()
    print("Done! The VPE is ready.")
    print(f"Path: {output_vpe}")
    print()
    print("Next: restart the STASIS server to pick up the new VPE:")
    print("  Your server auto-loads via STASIS_ULTRALYTICS_VPE_PATH")

    return 0


if __name__ == "__main__":
    sys.exit(main())

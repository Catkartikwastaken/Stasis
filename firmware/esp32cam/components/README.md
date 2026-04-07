# ESP-IDF Components for STASIS ESP32-CAM

This directory holds **extra ESP-IDF components** that are not available
through the ESP-IDF Component Manager (`idf_component.yml`).

## Required: esp-dl (for ESP-WHO Face Detection)

The MTMN face detection model lives in the **esp-dl** component from
Espressif's ESP-WHO project.  Without it, the firmware compiles and runs
but only uses **motion detection** (no face confirmation).

### Setup Instructions

```bash
# From the firmware/esp32cam/ directory:

# Option A: Clone esp-dl directly (recommended)
cd components
git clone --depth 1 --branch v0.9.0 \
    https://github.com/espressif/esp-dl.git

# Option B: Clone full ESP-WHO and symlink
git clone --recursive https://github.com/espressif/esp-who.git /tmp/esp-who
cp -r /tmp/esp-who/components/esp-dl components/
```

### Verify Installation

After setup, you should have:

```
components/
└── esp-dl/
    ├── CMakeLists.txt
    ├── include/
    │   ├── fd_forward.h          ← MTMN face detection API
    │   ├── dl_lib_matrix3d.h     ← Matrix operations
    │   └── ...
    └── ...
```

### Build Verification

```bash
# Build the project:
pio run

# If esp-dl is installed correctly, you'll see:
#   "Detector initialized (ESP-WHO MTMN face detection enabled)"
#
# If esp-dl is NOT installed, you'll see a compile warning:
#   "fd_forward.h not found — face detection disabled"
#   and the firmware runs in motion-only mode.
```

## Component Manager Dependencies

The following components are automatically resolved by the ESP-IDF
Component Manager (declared in `src/idf_component.yml`):

| Component              | Source                          | Purpose                    |
|------------------------|---------------------------------|----------------------------|
| `espressif/esp32-camera` | Component Registry            | Camera driver              |

## Troubleshooting

### "fd_forward.h: No such file or directory"
→ esp-dl is not installed.  Follow the setup instructions above.

### PSRAM allocation fails
→ Ensure `sdkconfig.defaults` has `CONFIG_ESP32_SPIRAM_SUPPORT=y`.
   Run `pio run -t menuconfig` and verify PSRAM is enabled.

### Face detection always returns no faces
→ The camera must be in **RGB565** mode (not JPEG).
   Check that `pixel_format = PIXFORMAT_RGB565` in `app_main.c`.
→ Ensure adequate lighting — MTMN needs reasonable contrast.

# Dataset Capture Assistant

Use this tool to take training photos with the webcam in a simple manual workflow. It opens a persistent desktop app, shows what kind of scene to capture next, and saves photos without closing the app.

## Install

From the repo root:

```powershell
python -m pip install opencv-python numpy pillow
```

## Start

```powershell
python tools\dataset_capture_assistant.py
```

Pick the class from the dropdown, then follow the on-screen prompts.

You can also start a class directly:

```powershell
python tools\dataset_capture_assistant.py --class-name red_strip
python tools\dataset_capture_assistant.py --class-name alpha_tester_object
python tools\dataset_capture_assistant.py --class-name empty_background
```

Images are saved to:

```text
C:\Users\<you>\Pictures\STASIS_Dataset\raw\<class_name>\
```

Use the `Choose Folder` button if you want another save location.

## Controls

```text
Space/C = capture now
N = next idea
L = next location
R = delete last saved image
Q = quit
```

## Camera Settings

The app lets you change common webcam settings without editing code:

```text
camera index
width
height
FPS
brightness
contrast
exposure
focus
```

The camera/settings sidebar is scrollable. Use the mouse wheel if the lower settings are outside the window.

It also shows:

```text
current resolution
estimated megapixels
camera backend
current property values
```

Most webcams do not report live electrical power usage through normal camera drivers, so the app shows power draw as unavailable when the camera does not expose it.

## Recommended Use

For the current demo dataset, use:

```text
alpha_tester_object
red_strip
empty_background
```

Take roughly 200 total photos across 4 locations. Mix objects together naturally, but still take empty background photos so the model learns when nothing important is present.

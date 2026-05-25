# Dataset Capture Assistant

Use this tool to take training photos with the webcam in an ordered way. It opens a persistent desktop app, shows the next angle/position prompt, waits until the camera view is steady, then saves the photo automatically without closing the app.

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
python tools\dataset_capture_assistant.py --class-name person
python tools\dataset_capture_assistant.py --class-name animal_stand_in
python tools\dataset_capture_assistant.py --class-name track_mark
python tools\dataset_capture_assistant.py --class-name fire_card
python tools\dataset_capture_assistant.py --class-name demo_object
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
S = skip current prompt
R = delete last saved image
P = toggle auto capture
Q = quit
```

## How Auto Capture Works

Hold the object at the requested angle. When the camera view becomes steady, the tool starts a short countdown and saves the image.

Default behavior:

```text
5 photos per prompt
automatic save after the frame is steady
ordered prompts for angle, distance, lighting, and position
the app stays open after each save
```

## Recommended Use

For each class, try:

```text
50 images minimum
100 images recommended
```

Use the webcam at rover height for the best dataset. Phone photos can still be added later, but webcam images are most important for matching the demo view.

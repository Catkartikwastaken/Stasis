import sys
import os

# Ensure the server directory is in path if executed from root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from security_rover_server_windows import (
    detect,
    postprocess_detections,
    DETECTOR_BACKEND,
    VISION_ENABLED
)

def run_tests():
    print("Running detection post-processing tests...")
    
    # Pre-flight assertions to ensure AI safety state
    assert not VISION_ENABLED, "VISION_ENABLED must be False"
    assert DETECTOR_BACKEND == "none", "DETECTOR_BACKEND must be 'none'"

    # 1. detect(None) returns [] when DETECTOR_BACKEND="none"
    assert detect(None) == [], "detect(None) should return empty list"

    # 2. postprocess_detections([], 640, 480) returns []
    assert postprocess_detections([], 640, 480) == [], "Empty input should return empty list"

    # Base valid detection for 640x480 frame
    # A 100x100 box = 10,000 area. Frame is 307,200. Ratio = 3.2% (> 2%).
    valid_raw = {"label": "human", "confidence": 0.90, "bbox": [10, 10, 110, 110]}

    # 3. malformed detection is rejected
    malformed_raw = {"label": "human", "conf": 0.9} # missing bbox and wrong confidence key
    assert postprocess_detections([malformed_raw], 640, 480) == []

    # 4. empty label is rejected
    empty_label_raw = {"label": "", "confidence": 0.90, "bbox": [10, 10, 110, 110]}
    assert postprocess_detections([empty_label_raw], 640, 480) == []

    # 5. low confidence detection is rejected (threshold is 0.70)
    low_conf_raw = {"label": "human", "confidence": 0.69, "bbox": [10, 10, 110, 110]}
    assert postprocess_detections([low_conf_raw], 640, 480) == []

    # 6. invalid bbox is rejected (x2 < x1)
    invalid_bbox_raw = {"label": "human", "confidence": 0.90, "bbox": [110, 10, 10, 110]}
    assert postprocess_detections([invalid_bbox_raw], 640, 480) == []

    # 7. bbox outside frame is rejected (x2 > 640)
    outside_bbox_raw = {"label": "human", "confidence": 0.90, "bbox": [10, 10, 650, 110]}
    assert postprocess_detections([outside_bbox_raw], 640, 480) == []

    # 8. tiny bbox under 2% frame area is rejected
    # 20x20 = 400 area. Ratio = 400/307200 = 0.13% (< 2%)
    tiny_bbox_raw = {"label": "human", "confidence": 0.90, "bbox": [10, 10, 30, 30]}
    assert postprocess_detections([tiny_bbox_raw], 640, 480) == []

    # 9. valid bbox is accepted
    res = postprocess_detections([valid_raw], 640, 480)
    assert len(res) == 1
    assert res[0]["label"] == "human"
    assert res[0]["confidence"] == 0.90
    assert res[0]["bbox"] == [10.0, 10.0, 110.0, 110.0]

    print("All detection post-processing tests passed.")

if __name__ == "__main__":
    run_tests()

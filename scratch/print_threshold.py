import sys
from pathlib import Path
import cv2
import numpy as np

def print_thresh():
    ROOT = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(ROOT))
    
    from app.omr.pipeline import load_image
    from app.omr.anchors import find_anchors, warp_perspective

    pdf_path = Path("/tmp/omr_uploads/BQACAgIAAxkBAAO7aiJZI7X4mhb0ueBHibN20fRi3AQAAjuRAAJdmBhJAXBUZkksdIc7BA.pdf")
    images = load_image(pdf_path)
    gray = images[0]
    anchor_centers = find_anchors(gray)
    if anchor_centers is None:
        print("Anchors not found")
        return
    warped_gray = warp_perspective(gray, anchor_centers, 1654, 2339)
    
    # Run Otsu thresholding
    blurred = cv2.GaussianBlur(warped_gray, (5, 5), 0)
    thresh_val, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    print(f"Otsu Threshold Value: {thresh_val}")
    print(f"Warped Gray image: min={np.min(warped_gray)}, max={np.max(warped_gray)}, mean={np.mean(warped_gray):.2f}")
    print(f"Binary image: count of 255 (white/foreground) pixels: {np.sum(binary == 255)}")
    print(f"Binary image: count of 0 (black/background) pixels: {np.sum(binary == 0)}")

if __name__ == "__main__":
    print_thresh()

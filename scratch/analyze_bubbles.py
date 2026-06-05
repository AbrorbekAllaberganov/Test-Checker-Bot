import sys
from pathlib import Path
import cv2
import numpy as np

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.omr.pipeline import load_image, preprocess
from app.omr.anchors import find_anchors, warp_perspective
from app.omr.layout import omr_grid_px

def analyze():
    pdf_path = "/tmp/omr_uploads/BQACAgIAAxkBAAO7aiJZI7X4mhb0ueBHibN20fRi3AQAAjuRAAJdmBhJAXBUZkksdIc7BA.pdf"
    print(f"Loading {pdf_path}...")
    images = load_image(pdf_path)
    gray = images[0]
    
    print("Finding anchors...")
    anchor_centers = find_anchors(gray)
    if anchor_centers is None:
        print("Error: anchors not found")
        return
        
    print("Warping perspective...")
    warped_gray = warp_perspective(gray, anchor_centers, 1654, 2339)
    
    print("Preprocessing (binary)...")
    warped_bin = preprocess(warped_gray)
    
    # Let's inspect some questions
    grid = omr_grid_px(40, dpi=200)
    from collections import defaultdict
    by_q = defaultdict(list)
    for cell in grid:
        by_q[cell["q"]].append(cell)
        
    questions_to_inspect = [1, 6, 16, 17]
    for qno in questions_to_inspect:
        print(f"\n=== Question {qno} ===")
        cells = by_q[qno]
        for cell in cells:
            cx, cy, r = int(cell["cx"]), int(cell["cy"]), int(cell["r"])
            letter = cell["letter"]
            
            # Extract ROI
            # Let's get a square of size 2*r around cx, cy
            x1, y1 = max(0, cx - int(r)), max(0, cy - int(r))
            x2, y2 = min(warped_gray.shape[1], cx + int(r)), min(warped_gray.shape[0], cy + int(r))
            
            roi_gray = warped_gray[y1:y2, x1:x2]
            roi_bin = warped_bin[y1:y2, x1:x2]
            
            # Calculate inner circle stats
            mask = np.zeros_like(warped_bin)
            inner_r = max(1, int(r * 0.8))
            cv2.circle(mask, (cx, cy), inner_r, 255, -1)
            
            # Grayscale values inside the circle mask
            pixels_gray = warped_gray[mask == 255]
            pixels_bin = warped_bin[mask == 255]
            
            mean_gray = np.mean(pixels_gray)
            min_gray = np.min(pixels_gray)
            max_gray = np.max(pixels_gray)
            fill_pct = np.count_nonzero(pixels_bin) / len(pixels_bin) if len(pixels_bin) > 0 else 0
            
            print(f"  Option {letter}:")
            print(f"    Grayscale: mean={mean_gray:.1f}, min={min_gray}, max={max_gray}")
            print(f"    Binary: fill_ratio={fill_pct:.3f}")
            
if __name__ == "__main__":
    analyze()

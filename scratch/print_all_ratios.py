import sys
from pathlib import Path
import cv2
import numpy as np

def print_all(file_name: str):
    ROOT = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(ROOT))
    
    from app.omr.pipeline import load_image, preprocess
    from app.omr.anchors import find_anchors, warp_perspective
    from app.omr.layout import omr_grid_px

    pdf_path = Path("/tmp/omr_uploads") / file_name
    if not pdf_path.exists():
        print(f"File not found: {pdf_path}")
        return
        
    print(f"Analyzing: {file_name}")
    images = load_image(pdf_path)
    gray = images[0]
    anchor_centers = find_anchors(gray)
    if anchor_centers is None:
        print("Anchors not found")
        return
    warped_gray = warp_perspective(gray, anchor_centers, 1654, 2339)
    
    grid = omr_grid_px(40, dpi=200)
    from collections import defaultdict
    by_q = defaultdict(list)
    for cell in grid:
        by_q[cell["q"]].append(cell)
        
    print("Q# | A_mean | B_mean | C_mean | D_mean | Min_Option")
    print("-" * 55)
    for qno in sorted(by_q.keys()):
        cells = by_q[qno]
        means = {}
        for cell in cells:
            cx, cy, r = int(cell["cx"]), int(cell["cy"]), int(cell["r"])
            letter = cell["letter"]
            
            mask = np.zeros_like(warped_gray)
            inner_r = max(1, int(r * 0.8))
            cv2.circle(mask, (cx, cy), inner_r, 255, -1)
            
            pixels = warped_gray[mask == 255]
            mean_val = np.mean(pixels) if len(pixels) > 0 else 255.0
            means[letter] = round(mean_val, 1)
            
        # Find which option is the darkest (lowest mean value)
        sorted_options = sorted(means.items(), key=lambda x: x[1])
        darkest_opt, darkest_val = sorted_options[0]
        second_darkest_opt, second_darkest_val = sorted_options[1]
        
        contrast = second_darkest_val - darkest_val
        is_marked = darkest_val < 220 # higher threshold
        
        mark_status = f"{darkest_opt} (val={darkest_val}, contrast={contrast:.1f})" if is_marked else "None"
        print(f"Q{qno:02d} | A={means.get('A', 255.0):5.1f} | B={means.get('B', 255.0):5.1f} | C={means.get('C', 255.0):5.1f} | D={means.get('D', 255.0):5.1f} | Marked: {mark_status}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        print_all(sys.argv[1])
    else:
        print_all("BQACAgIAAxkBAAO7aiJZI7X4mhb0ueBHibN20fRi3AQAAjuRAAJdmBhJAXBUZkksdIc7BA.pdf")

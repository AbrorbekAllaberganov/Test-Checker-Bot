import sys
from pathlib import Path
import cv2
import numpy as np

def check_alignment(file_name: str):
    ROOT = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(ROOT))
    
    from app.omr.pipeline import load_image
    from app.omr.anchors import find_anchors, warp_perspective
    from app.omr.layout import omr_grid_px

    pdf_path = Path("/tmp/omr_uploads") / file_name
    if not pdf_path.exists():
        print(f"File not found: {pdf_path}")
        return
        
    images = load_image(pdf_path)
    gray = images[0]
    anchor_centers = find_anchors(gray)
    if anchor_centers is None:
        print("Anchors not found")
        return
    warped_gray = warp_perspective(gray, anchor_centers, 1654, 2339)
    
    grid = omr_grid_px(40, dpi=200)
    
    print(f"Checking alignment on: {file_name}")
    print("Q# | Option | Expected (cx, cy) | Darkest Point (mx, my) | Offset (dx, dy) | Val")
    print("-" * 80)
    
    # We will search in a 50x50 box around each expected bubble center
    box_size = 25
    found_shifts = []
    
    for cell in grid:
        cx, cy, r = int(cell["cx"]), int(cell["cy"]), int(cell["r"])
        qno = cell["q"]
        letter = cell["letter"]
        
        y1, y2 = max(0, cy - box_size), min(warped_gray.shape[0], cy + box_size)
        x1, x2 = max(0, cx - box_size), min(warped_gray.shape[1], cx + box_size)
        
        roi = warped_gray[y1:y2, x1:x2]
        if roi.size == 0:
            continue
            
        min_val, _, min_loc, _ = cv2.minMaxLoc(roi)
        
        # If the minimum value is quite dark (e.g. < 130), it is likely a mark or a printed boundary
        if min_val < 130:
            mx = x1 + min_loc[0]
            my = y1 + min_loc[1]
            dx = mx - cx
            dy = my - cy
            print(f"Q{qno:02d} |   {letter}    | ({cx:4d}, {cy:4d})     | ({mx:4d}, {my:4d})       | ({dx:3d}, {dy:3d})     | {min_val:.0f}")
            found_shifts.append((dx, dy))
            
    if found_shifts:
        avg_dx = np.mean([s[0] for s in found_shifts])
        avg_dy = np.mean([s[1] for s in found_shifts])
        print("-" * 80)
        print(f"Average detected shift: dx = {avg_dx:.2f} px, dy = {avg_dy:.2f} px")
    else:
        print("No dark points found")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        check_alignment(sys.argv[1])
    else:
        check_alignment("BQACAgIAAxkBAAO7aiJZI7X4mhb0ueBHibN20fRi3AQAAjuRAAJdmBhJAXBUZkksdIc7BA.pdf")

import sys
from pathlib import Path
import cv2
import numpy as np

def find_bubbles():
    ROOT = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(ROOT))
    
    from app.omr.pipeline import load_image
    from app.omr.anchors import find_anchors, warp_perspective
    from app.omr.layout import omr_grid_px

    pdf_path = Path("/tmp/omr_uploads/BQACAgIAAxkBAAO7aiJZI7X4mhb0ueBHibN20fRi3AQAAjuRAAJdmBhJAXBUZkksdIc7BA.pdf")
    images = load_image(pdf_path)
    gray = images[0]
    anchor_centers = find_anchors(gray)
    if anchor_centers is None:
        print("Anchors not found")
        return
    warped_gray = warp_perspective(gray, anchor_centers, 1654, 2339)
    
    # Let's binarize to find circles
    # We invert it: background becomes dark, outlines become light
    _, thresh = cv2.threshold(warped_gray, 200, 255, cv2.THRESH_BINARY_INV)
    
    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    print(f"Total contours found: {len(contours)}")
    
    detected_circles = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        # For r = 23 px, area = pi * r^2 = ~1660 px^2.
        # Let's filter contours with area between 800 and 3000
        if 800 < area < 3000:
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
            
            # Check circularity: 4 * pi * area / perimeter^2
            circularity = 4 * np.pi * area / (peri * peri) if peri > 0 else 0
            if circularity > 0.6:
                # Get bounding box or minimum enclosing circle
                (x, y), radius = cv2.minEnclosingCircle(cnt)
                detected_circles.append((x, y, radius))
                
    print(f"Detected potential bubble circles: {len(detected_circles)}")
    
    # Now let's match them to our grid
    grid = omr_grid_px(40, dpi=200)
    print(f"Layout expected grid size: {len(grid)}")
    
    # For a few expected cells, let's find the nearest detected circle
    matches = []
    for cell in grid[:10]: # Check first 10 expected bubbles
        cx, cy = cell["cx"], cell["cy"]
        # Find nearest
        nearest = None
        min_dist = 9999.0
        for dc in detected_circles:
            dist = np.hypot(dc[0] - cx, dc[1] - cy)
            if dist < min_dist:
                min_dist = dist
                nearest = dc
                
        if nearest and min_dist < 100: # within 100 px
            dx = nearest[0] - cx
            dy = nearest[1] - cy
            matches.append((dx, dy))
            print(f"Cell Q{cell['q']}{cell['letter']} expected ({cx:.1f}, {cy:.1f}) -> nearest detected ({nearest[0]:.1f}, {nearest[1]:.1f}) | Offset: (dx={dx:.1f}, dy={dy:.1f}) | Dist: {min_dist:.1f}")
            
    if matches:
        mean_dx = np.mean([m[0] for m in matches])
        mean_dy = np.mean([m[1] for m in matches])
        print(f"\nAverage Grid Shift detected: dx={mean_dx:.1f} px, dy={mean_dy:.1f} px")
    else:
        print("No matches found")

if __name__ == "__main__":
    find_bubbles()

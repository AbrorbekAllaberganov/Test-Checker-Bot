import sys
from pathlib import Path
import cv2
import numpy as np

def debug_coords():
    ROOT = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(ROOT))
    
    from app.omr.pipeline import load_image, preprocess
    from app.omr.anchors import find_anchors, warp_perspective
    from app.omr.layout import ANCHOR_CENTER_OFFSET_MM, PAGE_W_MM, PAGE_H_MM

    # Correct scale computation
    W, H = 1654, 2339
    off = ANCHOR_CENTER_OFFSET_MM
    usable_w = PAGE_W_MM - 2 * off
    usable_h = PAGE_H_MM - 2 * off
    kx = W / usable_w
    ky = H / usable_h
    
    pdf_path = Path("/tmp/omr_uploads/BQACAgIAAxkBAAO7aiJZI7X4mhb0ueBHibN20fRi3AQAAjuRAAJdmBhJAXBUZkksdIc7BA.pdf")
    images = load_image(pdf_path)
    gray = images[0]
    anchor_centers = find_anchors(gray)
    if anchor_centers is None:
        print("Anchors not found")
        return
    warped_gray = warp_perspective(gray, anchor_centers, W, H)
    warped_bin = preprocess(warped_gray)
    
    # Q01D: x0=35, y0=60, dx=9, dy=8.5, d=6, j=3 (D)
    cx_mm = 35 + 3 * 9 + 6/2
    cy_mm = 60 + 0 * 8.5 + 6/2
    cx = (cx_mm - off) * kx
    cy = (cy_mm - off) * ky
    r = (6/2) * kx
    
    print(f"Q01D float coords: cx={cx:.2f}, cy={cy:.2f}, r={r:.2f}")
    cx_int, cy_int, r_int = int(cx), int(cy), int(r)
    print(f"Q01D int coords: cx={cx_int}, cy={cy_int}, r={r_int}")
    
    # Crop a 10x10 area around cx_int, cy_int
    crop_gray = warped_gray[cy_int-5:cy_int+5, cx_int-5:cx_int+5]
    crop_bin = warped_bin[cy_int-5:cy_int+5, cx_int-5:cx_int+5]
    
    print("\nCrop Gray:")
    print(crop_gray)
    print("\nCrop Binary:")
    print(crop_bin)
    
    # Calculate mask and fill
    mask = np.zeros_like(warped_bin)
    inner_r = max(1, int(r * 0.8))
    cv2.circle(mask, (cx_int, cy_int), inner_r, 255, -1)
    
    area = cv2.countNonZero(mask)
    intersect = cv2.bitwise_and(warped_bin, mask)
    filled = cv2.countNonZero(intersect)
    
    print(f"\nMask inner_r: {inner_r}")
    print(f"Mask area: {area}")
    print(f"Intersect count: {filled}")
    print(f"Ratio: {filled/area if area > 0 else 0}")

if __name__ == "__main__":
    debug_coords()

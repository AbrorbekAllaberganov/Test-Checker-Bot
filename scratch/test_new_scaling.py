import sys
from pathlib import Path
import cv2
import numpy as np

def test_new_scaling():
    ROOT = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(ROOT))
    
    from app.omr.pipeline import load_image, preprocess
    from app.omr.anchors import find_anchors, warp_perspective
    from app.omr.layout import LAYOUTS_MM, ANCHOR_CENTER_OFFSET_MM, PAGE_W_MM, PAGE_H_MM
    from app.omr.bubbles import decide_answer

    # 1. Correct scale computation
    W, H = 1654, 2339
    off = ANCHOR_CENTER_OFFSET_MM
    usable_w = PAGE_W_MM - 2 * off
    usable_h = PAGE_H_MM - 2 * off
    
    kx = W / usable_w
    ky = H / usable_h
    
    print(f"Correct scales: kx = {kx:.5f} px/mm, ky = {ky:.5f} px/mm")
    
    # Generate new grid coordinates using the correct scale
    def new_omr_grid_px(qcount: int, vcount: int = 4) -> list[dict]:
        L = LAYOUTS_MM[qcount]
        options = L["options"][:vcount]
        out = []
        for b in L["blocks"]:
            for i in range(b["count"]):
                qno = b["start"] + i
                for j, letter in enumerate(options):
                    cx_mm = b["x0"] + j * b["dx"] + b["d"] / 2
                    cy_mm = b["y0"] + i * b["dy"] + b["d"] / 2
                    
                    # Convert to warped space pixel coordinates
                    cx_px = (cx_mm - off) * kx
                    cy_px = (cy_mm - off) * ky
                    r_px = (b["d"] / 2) * kx # width scale for radius
                    
                    out.append({
                        "q": qno,
                        "letter": letter,
                        "cx": round(cx_px, 1),
                        "cy": round(cy_px, 1),
                        "r": round(r_px, 1),
                    })
        return out

    pdf_path = Path("/tmp/omr_uploads/BQACAgIAAxkBAAO7aiJZI7X4mhb0ueBHibN20fRi3AQAAjuRAAJdmBhJAXBUZkksdIc7BA.pdf")
    images = load_image(pdf_path)
    gray = images[0]
    anchor_centers = find_anchors(gray)
    if anchor_centers is None:
        print("Anchors not found")
        return
    warped_gray = warp_perspective(gray, anchor_centers, W, H)
    warped_bin = preprocess(warped_gray)
    
    # Evaluate with new coordinates
    grid = new_omr_grid_px(40)
    
    # Savol bo'yicha guruhlash
    from collections import defaultdict
    by_q = defaultdict(list)
    for cell in grid:
        by_q[cell["q"]].append(cell)
        
    def fill_ratio_local(bin_img, cx, cy, r):
        mask = np.zeros_like(bin_img)
        inner_r = max(1, int(r * 0.8))
        cv2.circle(mask, (int(cx), int(cy)), inner_r, 255, -1)
        area = cv2.countNonZero(mask)
        if area == 0:
            return 0.0
        filled = cv2.countNonZero(cv2.bitwise_and(bin_img, mask))
        return filled / area

    print("\nCorrected OMR Check:")
    print("Q# | Answer | Ratios")
    print("-" * 40)
    for qno in sorted(by_q.keys()):
        cells = by_q[qno]
        letters = [c["letter"] for c in cells]
        ratios = [
            fill_ratio_local(warped_bin, c["cx"], c["cy"], c["r"])
            for c in cells
        ]
        answer, conf, flag = decide_answer(ratios, letters, fill_min=0.35, fill_margin=0.15)
        ratios_str = ", ".join(f"{l}: {r:.3f}" for l, r in zip(letters, ratios))
        print(f"Q{qno:02d} | {str(answer):4s} (flag={flag}) | {ratios_str}")

if __name__ == "__main__":
    test_new_scaling()

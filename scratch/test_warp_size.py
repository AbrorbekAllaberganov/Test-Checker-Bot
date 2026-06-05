import sys
from pathlib import Path
import cv2
import numpy as np

def test_warp_size(file_name: str):
    ROOT = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(ROOT))
    
    from app.omr.pipeline import run
    from app.core.config import get_settings

    pdf_path = Path("/tmp/omr_uploads") / file_name
    if not pdf_path.exists():
        print(f"File not found: {pdf_path}")
        return
        
    print(f"\n================== Running OMR with warp_w=1449, warp_h=2134 on {file_name} ==================")
    results = run(
        pdf_path,
        fill_min=0.35,
        fill_margin=0.15,
        warp_w=1449,
        warp_h=2134,
        omr_dpi=200,
        omr_debug=False,
        qcount=40,
    )
    
    if not results:
        print("No results returned.")
        return
        
    res = results[0]
    if res.error:
        print(f"Error: {res.error}")
        return
        
    print(f"Titul UUID: {res.titul_uuid}")
    print(f"Needs Review: {res.needs_review}")
    print("Detected answers:")
    for q in sorted(res.detected.keys(), key=int):
        ans = res.detected[q]
        bd = res.bubble_data[q]
        if ans is not None:
            print(f"  Q{q}: {ans} (conf: {bd['conf']:.3f}, ratios: {bd['ratios']})")
        else:
            # Print blank details if there's any hint of a mark
            max_r = max(bd['ratios'].values())
            if max_r > 0.15:
                print(f"  Q{q}: Blank (max ratio {max_r:.3f}, ratios: {bd['ratios']})")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_warp_size(sys.argv[1])
    else:
        # Run on the three files we checked earlier
        files = [
            "BQACAgIAAxkBAAO7aiJZI7X4mhb0ueBHibN20fRi3AQAAjuRAAJdmBhJAXBUZkksdIc7BA.pdf",
            "BQACAgIAAxkBAAO4aiJYl1qtS5BEfr07KinOHwAB0ox9AAI2kQACXZgYSVaTfeUrvZuAOwQ.pdf",
            "BQACAgIAAxkBAAN2aiF481-DSAs7Nr35coRxuolv2vMAAieiAAKS2hBJlG-VtBmIsz07BA.pdf"
        ]
        for f in files:
            test_warp_size(f)

import sys
from pathlib import Path
import logging

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO)

from app.omr.pipeline import run
from app.core.config import get_settings

def test_file(file_name: str):
    file_path = Path("/tmp/omr_uploads") / file_name
    if not file_path.exists():
        print(f"File not found in container: {file_path}")
        return

    print(f"Running OMR on {file_path}...")
    settings = get_settings()
    
    results = run(
        file_path,
        fill_min=settings.fill_min,
        fill_margin=settings.fill_margin,
        warp_w=settings.warp_w,
        warp_h=settings.warp_h,
        omr_dpi=settings.omr_dpi,
        omr_debug=True,
        debug_out_dir=Path("/data/debug"),
        # Use default qcount or auto-detect if possible
        qcount=40, # Let's try 40 first
    )
    
    if not results:
        print("No results returned.")
        return
        
    for idx, res in enumerate(results):
        print(f"\n--- Page {idx} ---")
        if res.error:
            print(f"Error: {res.error}")
            continue
        print(f"Titul UUID: {res.titul_uuid}")
        print(f"Needs Review: {res.needs_review}")
        print("Detected answers:")
        for q in sorted(res.detected.keys(), key=int):
            ans = res.detected[q]
            bd = res.bubble_data[q]
            print(f"  Q{q}: {ans} (conf: {bd['conf']}, flag: {bd['flag']}, ratios: {bd['ratios']})")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_file(sys.argv[1])
    else:
        # Default to the most recent one
        test_file("BQACAgIAAxkBAAO7aiJZI7X4mhb0ueBHibN20fRi3AQAAjuRAAJdmBhJAXBUZkksdIc7BA.pdf")

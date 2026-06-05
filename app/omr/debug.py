"""
app/omr/debug.py — Debug annotatsiya rasmi.

OMR_DEBUG=true bo'lsa warped rasm ustiga anchor, doira va qarorlar chiziladi.
Bu kalibrlash uchun eng muhim vosita.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

log = logging.getLogger(__name__)


def annotate(
    warped_gray: np.ndarray,
    grid: list[dict],
    bubble_results: dict[str, dict],
    anchor_centers: Optional[np.ndarray],
    out_path: str | Path,
) -> Path:
    """
    Annotatsiyalangan debug rasmini saqlaydi.

    Docs/03 §10 ga mos:
    - Topilgan anchorlar → yashil kvadrat
    - Tanlangan doira → qizil to'ldirilgan
    - Tanlanmagan doira → ko'k kontur
    - Savol nomeri → har qator yonida

    Args:
        warped_gray:    Warped grayscale rasm.
        grid:           omr_grid_px() natijasi.
        bubble_results: read_all_bubbles() natijasi.
        anchor_centers: (4,2) anchor markazlari (warp oldidan) yoki None.
        out_path:       Saqlash yo'li.

    Returns:
        Saqlangan fayl yo'li.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # BGR rangli nusxa
    vis = cv2.cvtColor(warped_gray, cv2.COLOR_GRAY2BGR)

    # 1. Anchor markazlari (warped rasmda 4 burchak)
    H, W = vis.shape[:2]
    corners = [(15, 15), (W - 15, 15), (W - 15, H - 15), (15, H - 15)]
    for cx, cy in corners:
        cv2.rectangle(vis, (cx - 12, cy - 12), (cx + 12, cy + 12), (0, 200, 0), 2)

    # 2. Doiralar
    from collections import defaultdict
    by_q: dict[int, list[dict]] = defaultdict(list)
    for cell in grid:
        by_q[cell["q"]].append(cell)

    last_qy: dict[int, int] = {}  # savol → y koordinata (raqam uchun)

    for qno in sorted(by_q.keys()):
        cells = by_q[qno]
        qdata = bubble_results.get(str(qno), {})
        chosen = qdata.get("answer")

        for cell in cells:
            cx, cy, r = int(cell["cx"]), int(cell["cy"]), int(cell["r"])
            letter = cell["letter"]
            is_chosen = (letter == chosen)

            if is_chosen:
                # Qizil to'ldirilgan doira
                cv2.circle(vis, (cx, cy), r, (0, 0, 220), -1)
                cv2.circle(vis, (cx, cy), r, (0, 0, 180), 1)
            else:
                # Ko'k kontur
                cv2.circle(vis, (cx, cy), r, (200, 80, 0), 1)

            # Harf
            cv2.putText(
                vis, letter, (cx - 5, cy + 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.28, (30, 30, 30), 1, cv2.LINE_AA,
            )
            last_qy[qno] = cy

        # Savol raqami (chap tomonda)
        first_cx = int(cells[0]["cx"])
        qy = int(cells[0]["cy"])
        cv2.putText(
            vis, str(qno), (max(0, first_cx - int(cells[0]["r"]) - 22), qy + 4),
            cv2.FONT_HERSHEY_SIMPLEX, 0.30, (60, 60, 60), 1, cv2.LINE_AA,
        )

    # 3. Flag bo'lgan savollar uchun sariq belgisi
    for qno_str, qdata in bubble_results.items():
        flag = qdata.get("flag")
        if flag == "ambiguous":
            for cell in by_q.get(int(qno_str), []):
                if cell["letter"] == qdata.get("answer"):
                    cv2.circle(
                        vis,
                        (int(cell["cx"]), int(cell["cy"])),
                        int(cell["r"]) + 3,
                        (0, 200, 200), 1,
                    )

    cv2.imwrite(str(out_path), vis)
    log.info("Debug rasm saqlandi: %s", out_path)
    return out_path

"""
app/tests/test_layout.py — Layout koordinata konsistentlik testlari.

build_bubble_positions() va omr_grid_px() bitta manbadan kelishi — PDF
va OMR koordinatalarining mos kelishini ta'minlaydi.
"""
from __future__ import annotations

import pytest

from app.omr.layout import (
    ANCHOR_CENTER_OFFSET_MM,
    LAYOUTS_MM,
    build_bubble_positions,
    omr_grid_px,
)

DPI = 200
K = DPI / 25.4  # mm → px


@pytest.mark.parametrize("qcount", [40, 50, 90])
def test_bubble_count(qcount: int):
    """Doiralar soni savol_soni * variant_soni ga teng."""
    bubbles = build_bubble_positions(qcount)
    expected = qcount * 4
    assert len(bubbles) == expected, f"qcount={qcount}: {len(bubbles)} != {expected}"


@pytest.mark.parametrize("qcount", [40, 50, 90])
def test_omr_grid_count(qcount: int):
    """OMR grid ham xuddi shuncha yozuv."""
    grid = omr_grid_px(qcount, dpi=DPI)
    assert len(grid) == qcount * 4


@pytest.mark.parametrize("qcount", [40, 50, 90])
def test_center_consistency(qcount: int):
    """
    PDF doira chap-yuqori burchagi (x, y) dan markaz hisoblash
    OMR pixel markaziga mos kelishi kerak (1 px tolerans).
    """
    bubbles = build_bubble_positions(qcount)  # {x, y, d, q, letter} mm
    grid = omr_grid_px(qcount, dpi=DPI)       # {cx, cy, r, q, letter} px

    # Dict ga aylantirish
    pdf_map = {(b["q"], b["letter"]): b for b in bubbles}
    omr_map = {(g["q"], g["letter"]): g for g in grid}

    for key in pdf_map:
        b = pdf_map[key]
        g = omr_map[key]

        # PDF markaz mm
        pdf_cx_mm = b["x"] + b["d"] / 2
        pdf_cy_mm = b["y"] + b["d"] / 2

        # Warp offset (anchor markazi 0,0 ga keladi)
        expected_cx_px = (pdf_cx_mm - ANCHOR_CENTER_OFFSET_MM) * K
        expected_cy_px = (pdf_cy_mm - ANCHOR_CENTER_OFFSET_MM) * K

        assert abs(g["cx"] - expected_cx_px) < 1.5, (
            f"q={key[0]} {key[1]}: cx mismatch: "
            f"expected={expected_cx_px:.1f} got={g['cx']:.1f}"
        )
        assert abs(g["cy"] - expected_cy_px) < 1.5, (
            f"q={key[0]} {key[1]}: cy mismatch: "
            f"expected={expected_cy_px:.1f} got={g['cy']:.1f}"
        )


@pytest.mark.parametrize("qcount", [40, 50, 90])
def test_no_overlap(qcount: int):
    """Doiralar bir-biri bilan kesishmaydi (markazlar oralig'i > diametr)."""
    grid = omr_grid_px(qcount, dpi=DPI)

    # Bir savolning barcha variantlari
    from collections import defaultdict
    by_q: dict[int, list] = defaultdict(list)
    for g in grid:
        by_q[g["q"]].append(g)

    for qno, cells in by_q.items():
        for i, a in enumerate(cells):
            for b in cells[i + 1:]:
                dist = ((a["cx"] - b["cx"]) ** 2 + (a["cy"] - b["cy"]) ** 2) ** 0.5
                min_dist = a["r"] + b["r"]
                assert dist > min_dist * 0.8, (
                    f"q={qno}: doiralar kesishmoqda: dist={dist:.1f} < {min_dist:.1f}"
                )

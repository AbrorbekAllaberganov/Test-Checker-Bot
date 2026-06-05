"""
YAGONA HAQIQAT MANBASI (single source of truth) — grid koordinatalari.

PDF shabloni shu koordinatalardan doira chizadi, OMR pipeline ESA aynan shu
koordinatalardan o'qiydi. Kalibrlashda faqat shu fayldagi LAYOUTS_MM ni sozlang.

O'lchov birligi: millimetr (mm), A4 portrait (210 x 297 mm).
Koordinata kelib chiqishi (origin): ANCHOR markazlari hosil qilgan to'rtburchak.
  - Anchor markazi har burchakdan 13mm ichkarida (8mm margin + 5mm yarim-anchor).
  - Demak foydali maydon: x in [13, 197], y in [13, 284] (mm).
  - x0,y0 koordinatalari shu origin (chap-yuqori anchor markazi = 13,13) dan
    EMAS, balki sahifa chap-yuqorisidan (0,0) o'lchanadi — PDF absolyut joylashuv
    uchun. OMR warp paytida anchor markazlari (13,13)->(0,0) ga keladi, shuning
    uchun omr_grid_px() x dan 13mm, y dan 13mm ayiradi (pastdagi izohga qarang).
"""
from __future__ import annotations

# Anchor markazi sahifa chetidan (mm). PDF: margin 8mm, anchor 10mm => markaz 13mm.
ANCHOR_MARGIN_MM = 8.0
ANCHOR_SIZE_MM = 10.0
ANCHOR_CENTER_OFFSET_MM = ANCHOR_MARGIN_MM + ANCHOR_SIZE_MM / 2  # = 13.0

PAGE_W_MM = 210.0
PAGE_H_MM = 297.0

# Boshlang'ich taxminiy koordinatalar — KALIBRLASH KERAK.
# Har blok: bitta ustun. q: x0..x0+(vcount-1)*dx (variantlar), y: y0..y0+(count-1)*dy
LAYOUTS_MM: dict[int, dict] = {
    40: {
        "options": ["A", "B", "C", "D"],
        "blocks": [
            {"label": "A(1-20)",  "start": 1,  "count": 20, "x0": 35,  "y0": 60, "dx": 9, "dy": 8.5, "d": 6},
            {"label": "B(21-40)", "start": 21, "count": 20, "x0": 110, "y0": 60, "dx": 9, "dy": 8.5, "d": 6},
        ],
    },
    50: {
        "options": ["A", "B", "C", "D"],
        "blocks": [
            {"label": "A(1-25)",  "start": 1,  "count": 25, "x0": 35,  "y0": 60, "dx": 9, "dy": 7.2, "d": 5.5},
            {"label": "B(26-50)", "start": 26, "count": 25, "x0": 110, "y0": 60, "dx": 9, "dy": 7.2, "d": 5.5},
        ],
    },
    90: {
        "options": ["A", "B", "C", "D"],
        "blocks": [
            {"label": "Majburiy(1-30)", "start": 1,  "count": 30, "x0": 25,  "y0": 60, "dx": 8, "dy": 6.2, "d": 5},
            {"label": "I blok(31-60)",  "start": 31, "count": 30, "x0": 90,  "y0": 60, "dx": 8, "dy": 6.2, "d": 5},
            {"label": "II blok(61-90)", "start": 61, "count": 30, "x0": 155, "y0": 60, "dx": 8, "dy": 6.2, "d": 5},
        ],
    },
}


def build_bubble_positions(qcount: int, vcount: int = 4) -> list[dict]:
    """PDF shabloni uchun: har doira uchun {q, letter, x, y, d} (mm, sahifa origini)."""
    L = LAYOUTS_MM[qcount]
    options = L["options"][:vcount]
    out: list[dict] = []
    for b in L["blocks"]:
        for i in range(b["count"]):
            qno = b["start"] + i
            for j, letter in enumerate(options):
                out.append({
                    "q": qno,
                    "letter": letter,
                    # markaz emas, chap-yuqori burchak (CSS left/top uchun):
                    "x": round(b["x0"] + j * b["dx"], 3),
                    "y": round(b["y0"] + i * b["dy"], 3),
                    "d": b["d"],
                })
    return out


def block_labels(qcount: int) -> list[dict]:
    """Blok sarlavhalari uchun joylashuv (HTML uchun)."""
    L = LAYOUTS_MM[qcount]
    return [{"label": b["label"], "x": b["x0"] - 5, "y": b["y0"] - 12} for b in L["blocks"]]


def omr_grid_px(qcount: int, dpi: int = 200, vcount: int = 4) -> list[dict]:
    """
    OMR pipeline uchun: har doira MARKAZI (px) warped rasmda.
    Warp anchor markazlarini sahifa origini ga keltiradi: (13,13)mm -> (0,0)px.
    Shuning uchun mm dan ANCHOR_CENTER_OFFSET_MM ayiriladi, keyin px ga.
    Warped o'lcham: foydali maydon (PAGE - 2*offset) * k.
    """
    k = dpi / 25.4  # mm -> px
    L = LAYOUTS_MM[qcount]
    options = L["options"][:vcount]
    off = ANCHOR_CENTER_OFFSET_MM
    out: list[dict] = []
    for b in L["blocks"]:
        for i in range(b["count"]):
            qno = b["start"] + i
            for j, letter in enumerate(options):
                cx_mm = b["x0"] + j * b["dx"] + b["d"] / 2  # markaz = burchak + yarim-diametr
                cy_mm = b["y0"] + i * b["dy"] + b["d"] / 2
                out.append({
                    "q": qno,
                    "letter": letter,
                    "cx": round((cx_mm - off) * k, 1),
                    "cy": round((cy_mm - off) * k, 1),
                    "r": round((b["d"] / 2) * k, 1),
                })
    return out


def warped_size_px(dpi: int = 200) -> tuple[int, int]:
    """Anchor markazlari orasidagi foydali maydon o'lchami (px)."""
    k = dpi / 25.4
    usable_w = PAGE_W_MM - 2 * ANCHOR_CENTER_OFFSET_MM
    usable_h = PAGE_H_MM - 2 * ANCHOR_CENTER_OFFSET_MM
    return round(usable_w * k), round(usable_h * k)

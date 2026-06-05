"""
app/omr/bubbles.py — Doiralarni o'lchash (fill_ratio).

Docs/03 spetsifikatsiyasiga aniq mos:
  fill_ratio: circular mask → bitwise_and → filled/area
  read_all_bubbles: barcha grid doiralarini o'qiydi
"""
from __future__ import annotations

import logging
from typing import Optional

import cv2
import numpy as np

log = logging.getLogger(__name__)


def fill_ratio(
    warped_bin: np.ndarray,
    cx: int,
    cy: int,
    r: float,
) -> float:
    """
    Doira markazida to'ldirilganlik darajasi.

    warped_bin: 0/255 binary rasm (to'ldirilgan = OQ, fon = QORA).
    r * 0.8 radiusli niqob ishlatiladi (chegara piksellarni kamaytirish uchun).

    Args:
        warped_bin: Binary warped rasm (threshold + invert).
        cx, cy:     Doira markazi (px, int).
        r:          Doira radiusi (px).

    Returns:
        0.0 - 1.0 orasidagi float: 0=bo'sh, 1=to'liq to'ldirilgan.
    """
    mask = np.zeros_like(warped_bin)
    inner_r = max(1, int(r * 0.8))
    cv2.circle(mask, (int(cx), int(cy)), inner_r, 255, -1)

    area = cv2.countNonZero(mask)
    if area == 0:
        return 0.0

    filled = cv2.countNonZero(cv2.bitwise_and(warped_bin, mask))
    return filled / area


def decide_answer(
    ratios: list[float],
    letters: list[str],
    fill_min: float = 0.35,
    fill_margin: float = 0.15,
) -> tuple[Optional[str], float, Optional[str]]:
    """
    Variant tanlash: docs/03 §8 algoritmiga aniq mos.

    Args:
        ratios:      Har variant uchun fill_ratio ro'yxati.
        letters:     ["A","B","C","D"] (yoki N ta).
        fill_min:    Minimal to'ldirilganlik (bo'sh doira chegarasi).
        fill_margin: Ikkilanish chegarasi.

    Returns:
        (answer, confidence, flag)
        - answer: "A"..."D" yoki None (bo'sh)
        - confidence: max1 - max2
        - flag: None | "blank" | "ambiguous"
    """
    if not ratios:
        return None, 0.0, "blank"

    indexed = sorted(enumerate(ratios), key=lambda x: x[1], reverse=True)
    max1_idx, max1 = indexed[0]
    max2 = indexed[1][1] if len(indexed) > 1 else 0.0

    if max1 < fill_min:
        return None, max1, "blank"

    conf = max1 - max2
    if conf < fill_margin:
        # Ikkilanish — eng kattasini olamiz, lekin flag qo'yamiz
        return letters[max1_idx], conf, "ambiguous"

    return letters[max1_idx], conf, None


def read_all_bubbles(
    warped_bin: np.ndarray,
    grid: list[dict],
    fill_min: float = 0.35,
    fill_margin: float = 0.15,
) -> dict[str, dict]:
    """
    Barcha doiralarni o'qib, har savol uchun qaror qabul qiladi.

    Args:
        warped_bin: Binary warped rasm.
        grid:       omr_grid_px() natijasi — [{q, letter, cx, cy, r}, ...].
        fill_min:   Bo'sh chegarasi.
        fill_margin: Ikkilanish chegarasi.

    Returns:
        {
          "1": {
            "answer": "A" | None,
            "ratios": {"A": 0.7, "B": 0.1, ...},
            "conf": 0.6,
            "flag": None | "blank" | "ambiguous",
          }, ...
        }
    """
    # Savol bo'yicha guruhlashtirish
    from collections import defaultdict
    by_q: dict[int, list[dict]] = defaultdict(list)
    for cell in grid:
        by_q[cell["q"]].append(cell)

    results: dict[str, dict] = {}

    for qno in sorted(by_q.keys()):
        cells = by_q[qno]
        letters = [c["letter"] for c in cells]
        ratios = [
            fill_ratio(warped_bin, int(c["cx"]), int(c["cy"]), c["r"])
            for c in cells
        ]
        answer, conf, flag = decide_answer(ratios, letters, fill_min, fill_margin)
        results[str(qno)] = {
            "answer": answer,
            "ratios": {l: round(r, 4) for l, r in zip(letters, ratios)},
            "conf": round(conf, 4),
            "flag": flag,
        }

    return results

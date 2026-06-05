"""
app/omr/anchors.py — Anchor (fiducial) markerlarini topish va perspektiva to'g'rilash.

4 ta to'ldirilgan qora kvadrat varaqning 4 burchagida joylashgan.
Algoritm: threshold → findContours → kichik to'rtburchakli konturlarni filter →
4 ta eng kattasini ol → markazlarini tartibla (TL, TR, BR, BL) → warpPerspective.
"""
from __future__ import annotations

import logging
from typing import Optional

import cv2
import numpy as np

log = logging.getLogger(__name__)

# Anchor maydon oralig'i (piksel, ~ 200 DPI @ A4): min 50*50, max 300*300
ANCHOR_MIN_AREA = 2000
ANCHOR_MAX_AREA = 50_000
ANCHOR_ASPECT_TOL = 0.4   # aspect ratio |1 - w/h| < bu qiymat bo'lishi kerak


def order_points(pts: np.ndarray) -> np.ndarray:
    """
    4 ta nuqtani [TL, TR, BR, BL] tartibida qaytaradi.

    Docs/03 spetsifikatsiyasiga aniq mos (sum/diff usuli).

    Args:
        pts: (4, 2) float32 array.

    Returns:
        (4, 2) float32 array [TL, TR, BR, BL].
    """
    pts = pts.astype("float32")
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()

    tl = pts[np.argmin(s)]
    br = pts[np.argmax(s)]
    tr = pts[np.argmin(d)]
    bl = pts[np.argmax(d)]

    return np.array([tl, tr, br, bl], dtype="float32")


def find_anchors(gray: np.ndarray) -> Optional[np.ndarray]:
    """
    Rasmdan 4 ta anchor markazini topadi.

    Args:
        gray: Grayscale rasm (uint8).

    Returns:
        (4, 2) float32 array [TL, TR, BR, BL] piksel koordinatalar,
        yoki None (4 ta topilmasa).
    """
    # Invert threshold: qora kvadratlar → oq, fon → qora
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Kichik shovqinlarni yo'q qilish
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates: list[tuple[float, np.ndarray]] = []  # (area, center)

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if not (ANCHOR_MIN_AREA < area < ANCHOR_MAX_AREA):
            continue

        # Konturni to'rtburchakka yaqinlashtirish
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.04 * peri, True)

        if len(approx) != 4:
            continue

        # Aspect ratio: kvadratga yaqin bo'lishi kerak
        x, y, w, h = cv2.boundingRect(approx)
        if h == 0:
            continue
        aspect = w / h
        if abs(1 - aspect) > ASPECT_TOL_GLOBAL:
            continue

        # Markaz
        cx = x + w / 2
        cy = y + h / 2
        candidates.append((area, np.array([cx, cy], dtype="float32")))

    # Eng katta 4 tasini ol
    candidates.sort(key=lambda t: t[0], reverse=True)

    if len(candidates) < 4:
        log.warning(
            "Anchor topilmadi: %d ta mos kontur (kamida 4 kerak)", len(candidates)
        )
        return None

    centers = np.array([c[1] for c in candidates[:4]], dtype="float32")
    ordered = order_points(centers)
    log.debug("Anchorlar: TL=%s TR=%s BR=%s BL=%s", *ordered)
    return ordered


# Modul darajasida saqlangan toleranslik (find_anchors ichida foydalaniladi)
ASPECT_TOL_GLOBAL = ANCHOR_ASPECT_TOL


def warp_perspective(
    gray: np.ndarray,
    anchor_centers: np.ndarray,
    W: int,
    H: int,
) -> np.ndarray:
    """
    Perspektiva to'g'rilash: anchor markazlari → sobit o'lcham [W x H].

    Args:
        gray:           Grayscale manba rasm.
        anchor_centers: (4,2) [TL,TR,BR,BL] piksel koordinatalar.
        W:              Natija kengligi (px).
        H:              Natija balandligi (px).

    Returns:
        (H, W) warped grayscale rasm.
    """
    dst = np.array(
        [[0, 0], [W - 1, 0], [W - 1, H - 1], [0, H - 1]], dtype="float32"
    )
    M = cv2.getPerspectiveTransform(anchor_centers, dst)
    warped = cv2.warpPerspective(gray, M, (W, H))
    return warped

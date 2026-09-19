"""
app/omr/anchors.py — Anchor (fiducial) markerlarini topish va perspektiva to'g'rilash.

4 ta to'ldirilgan qora kvadrat varaqning 4 burchagida joylashgan.
Algoritm: threshold → findContours → kvadratga yaqin konturlarni filter →
kandidatlardan to'g'ri to'rtburchak hosil qiladigan 4 talikni tanlash →
markazlarini tartiblash (TL, TR, BR, BL) → warpPerspective.

Maydon filtri NISBIY (weaknesses.md №13): ilgari absolyut piksel oralig'i
(2000..50000) ishlatilardi — 12 MP telefon suratida haqiqiy anchor bu
oraliqdan oshib ketardi, past sifatli skanda esa QR finder kvadratlari
"anchor" bo'lib tushardi. Endi kutilgan maydon rasm o'lchamidan hisoblanadi.
"""
from __future__ import annotations

import itertools
import logging
from typing import Optional

import cv2
import numpy as np

from app.omr.layout import (
    ANCHOR_CENTER_OFFSET_MM,
    ANCHOR_SIZE_MM,
    PAGE_H_MM,
    PAGE_W_MM,
)

log = logging.getLogger(__name__)

ANCHOR_ASPECT_TOL = 0.4   # kvadratlik: |1 - w/h| < bu qiymat

# Anchor maydoni sahifa maydonining qancha ulushi (10x10mm / 210x297mm).
ANCHOR_AREA_FRACTION = (ANCHOR_SIZE_MM ** 2) / (PAGE_W_MM * PAGE_H_MM)
# Kutilgan maydondan necha barobar chetlashishga ruxsat (perspektiva, kesilgan
# fon, siyoh yoyilishi).
ANCHOR_AREA_MIN_K = 0.3
ANCHOR_AREA_MAX_K = 3.0
# Juda kichik konturlar (shovqin) — nisbiy filtrdan qat'i nazar rad etiladi.
ANCHOR_ABS_MIN_AREA = 150

# Anchor markazlari hosil qiladigan to'rtburchak nisbati (foydali maydon):
# (210 - 26) / (297 - 26) = 184 / 271 ≈ 0.679
USABLE_W_MM = PAGE_W_MM - 2 * ANCHOR_CENTER_OFFSET_MM
USABLE_H_MM = PAGE_H_MM - 2 * ANCHOR_CENTER_OFFSET_MM
QUAD_ASPECT = USABLE_W_MM / USABLE_H_MM
QUAD_ASPECT_TOL = 0.22          # nisbiy: |ratio/QUAD_ASPECT - 1| < tol
QUAD_SIDE_TOL = 0.15            # qarama-qarshi tomonlar farqi < 15%
# Nechta eng katta kandidat kombinatsiya qilib ko'riladi (C(8,4) = 70).
MAX_CANDIDATES = 8


def order_points(pts: np.ndarray) -> np.ndarray:
    """
    4 ta nuqtani [TL, TR, BR, BL] tartibida qaytaradi.

    Docs/03 spetsifikatsiyasiga aniq mos (sum/diff usuli).

    Eslatma: bu faqat RASM koordinatalari bo'yicha tartiblaydi — varaqning
    fizik yo'nalishini (180° burilganini) bilmaydi. Uni `pipeline.run_single`
    QR joylashuvi orqali aniqlaydi.

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


def quad_is_sane(ordered: np.ndarray) -> bool:
    """
    Tartiblangan 4 markaz haqiqatan varaq to'rtburchagimi?

    Tekshiruvlar:
      1. Qavariq (convex) — nuqtalar chalkashib ketmagan.
      2. Qarama-qarshi tomonlar uzunligi yaqin (< QUAD_SIDE_TOL).
      3. Eni/bo'yi nisbati A4 foydali maydoniga mos (≈0.68).

    Args:
        ordered: (4,2) [TL, TR, BR, BL].
    """
    tl, tr, br, bl = ordered
    top = float(np.linalg.norm(tr - tl))
    bottom = float(np.linalg.norm(br - bl))
    left = float(np.linalg.norm(bl - tl))
    right = float(np.linalg.norm(br - tr))

    if min(top, bottom, left, right) < 1.0:
        return False

    if abs(top - bottom) / max(top, bottom) > QUAD_SIDE_TOL:
        return False
    if abs(left - right) / max(left, right) > QUAD_SIDE_TOL:
        return False

    width = (top + bottom) / 2
    height = (left + right) / 2
    if height <= 0:
        return False

    ratio = width / height
    if abs(ratio / QUAD_ASPECT - 1) > QUAD_ASPECT_TOL:
        return False

    contour = ordered.astype(np.int32).reshape(-1, 1, 2)
    if not cv2.isContourConvex(contour):
        return False

    return True


def find_anchors(gray: np.ndarray) -> Optional[np.ndarray]:
    """
    Rasmdan 4 ta anchor markazini topadi.

    Args:
        gray: Grayscale rasm (uint8).

    Returns:
        (4, 2) float32 array [TL, TR, BR, BL] piksel koordinatalar,
        yoki None (mos 4 talik topilmasa).
    """
    img_area = float(gray.shape[0] * gray.shape[1])
    expected_area = img_area * ANCHOR_AREA_FRACTION
    min_area = max(ANCHOR_ABS_MIN_AREA, expected_area * ANCHOR_AREA_MIN_K)
    max_area = expected_area * ANCHOR_AREA_MAX_K

    # Invert threshold: qora kvadratlar → oq, fon → qora
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Kichik shovqinlarni yo'q qilish
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates: list[tuple[float, np.ndarray]] = []  # (area, center)

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if not (min_area < area < max_area):
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
        if abs(1 - aspect) > ANCHOR_ASPECT_TOL:
            continue

        # Markaz
        cx = x + w / 2
        cy = y + h / 2
        candidates.append((area, np.array([cx, cy], dtype="float32")))

    if len(candidates) < 4:
        log.warning(
            "Anchor topilmadi: %d ta mos kontur (kamida 4 kerak)", len(candidates)
        )
        return None

    # Eng kattalaridan boshlab kombinatsiyalarni sinaymiz: birinchi mos
    # to'rtburchak qabul qilinadi. Ilgari shunchaki eng katta 4 tasi olinardi —
    # QR finder kvadratlari oralab kirsa grid butunlay siljib ketardi.
    candidates.sort(key=lambda t: t[0], reverse=True)
    pool = candidates[:MAX_CANDIDATES]

    for combo in itertools.combinations(pool, 4):
        centers = np.array([c[1] for c in combo], dtype="float32")
        ordered = order_points(centers)
        # order_points takroriy nuqta qaytarishi mumkin (deformatsiyalangan
        # joylashuvda) — unda to'rtburchak yo'q.
        if len(np.unique(ordered, axis=0)) != 4:
            continue
        if quad_is_sane(ordered):
            log.debug("Anchorlar: TL=%s TR=%s BR=%s BL=%s", *ordered)
            return ordered

    log.warning(
        "Anchor to'rtburchagi topilmadi: %d kandidatdan mos 4 talik yo'q",
        len(pool),
    )
    return None


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
    M = cv2.getPerspectiveTransform(anchor_centers.astype("float32"), dst)
    warped = cv2.warpPerspective(gray, M, (W, H))
    return warped

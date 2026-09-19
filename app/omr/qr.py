"""
app/omr/qr.py — QR kodni o'qish.

Kutilayotgan payload formati: "OMR|v1|<uuid>"

QR faqat titul UUID'ni bermaydi — uning varaqdagi JOYLASHUVI ham kerak:
shablonda QR yuqori-o'ng burchakda, demak markazi orqali varaq 180° burilgani
aniqlanadi (weaknesses.md №13). Shu sababli `read_qr_located()` markazni ham
qaytaradi; `read_qr()` — eski, faqat UUID kerak bo'lgan joylar uchun.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np
from pyzbar.pyzbar import decode

log = logging.getLogger(__name__)


def read_qr_located(
    gray: np.ndarray,
) -> tuple[Optional[str], Optional[tuple[float, float]]]:
    """
    Grayscale rasmdan QR kodni va uning markazini o'qiydi.

    Args:
        gray: Grayscale numpy array (uint8).

    Returns:
        (uuid, (cx, cy)) — topilmasa (None, None).
        Koordinata manba rasm pikselida.
    """
    decoded = decode(gray)
    for d in decoded:
        try:
            text = d.data.decode("utf-8")
        except (UnicodeDecodeError, AttributeError):
            continue

        if not text.startswith("OMR|v1|"):
            log.debug("QR bor, lekin format noto'g'ri: %s", text[:60])
            continue

        parts = text.split("|")
        if len(parts) < 3 or not parts[2]:
            continue

        center = _center_of(d)
        log.debug("QR topildi: %s, markaz=%s", text, center)
        return parts[2], center

    log.warning("QR topilmadi")
    return None, None


def _center_of(decoded_obj) -> Optional[tuple[float, float]]:
    """pyzbar natijasidan QR markazini hisoblaydi (polygon → rect → None)."""
    polygon = getattr(decoded_obj, "polygon", None)
    if polygon:
        xs = [float(p.x) for p in polygon]
        ys = [float(p.y) for p in polygon]
        return sum(xs) / len(xs), sum(ys) / len(ys)

    rect = getattr(decoded_obj, "rect", None)
    if rect is not None:
        return (
            float(rect.left) + float(rect.width) / 2,
            float(rect.top) + float(rect.height) / 2,
        )
    return None


def read_qr(gray: np.ndarray) -> str | None:
    """
    Grayscale rasmdan QR kodni o'qiydi (faqat UUID).

    Args:
        gray: Grayscale numpy array (uint8).

    Returns:
        Titul UUID string ("OMR|v1|" prefix olib tashlangan),
        yoki topilmasa None.
    """
    return read_qr_located(gray)[0]

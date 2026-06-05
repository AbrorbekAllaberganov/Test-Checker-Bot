"""
app/omr/qr.py — QR kodni o'qish.

Kutilayotgan payload formati: "OMR|v1|<uuid>"
"""
from __future__ import annotations

import logging

import numpy as np
from pyzbar.pyzbar import decode

log = logging.getLogger(__name__)


def read_qr(gray: np.ndarray) -> str | None:
    """
    Grayscale rasmdan QR kodni o'qiydi.

    Args:
        gray: Grayscale numpy array (uint8).

    Returns:
        Titul UUID string ("OMR|v1|" prefix olib tashlangan),
        yoki topilmasa None.
    """
    decoded = decode(gray)
    for d in decoded:
        try:
            text = d.data.decode("utf-8")
        except (UnicodeDecodeError, AttributeError):
            continue

        if text.startswith("OMR|v1|"):
            parts = text.split("|")
            if len(parts) >= 3 and parts[2]:
                log.debug("QR topildi: %s", text)
                return parts[2]  # uuid
        else:
            log.debug("QR bor, lekin format noto'g'ri: %s", text[:60])

    log.warning("QR topilmadi")
    return None

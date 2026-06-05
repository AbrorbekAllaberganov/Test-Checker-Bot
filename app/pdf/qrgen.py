"""
app/pdf/qrgen.py — QR kodi generatsiya.

Payload formati: "OMR|v1|<titul_uuid>"
Natija: base64 PNG data URI (HTML <img src="..."> uchun).
"""
from __future__ import annotations

import base64
import io

import qrcode
from qrcode.image.pil import PilImage


def qr_payload(titul_uuid: str) -> str:
    """QR payload stringini yaratish."""
    return f"OMR|v1|{titul_uuid}"


def make_qr_data_uri(
    titul_uuid: str,
    box_size: int = 6,
    border: int = 2,
) -> str:
    """
    QR kod → base64 PNG data URI.

    Args:
        titul_uuid: Titul UUID string yoki UUID obyekti.
        box_size: Har box px o'lchami.
        border: Oq chegara kengayishi (modulda).

    Returns:
        'data:image/png;base64,...' string.
    """
    payload = qr_payload(str(titul_uuid))

    qr = qrcode.QRCode(
        version=None,         # auto
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(payload)
    qr.make(fit=True)

    img: PilImage = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"

"""
app/omr/pipeline.py — To'liq OMR oqimi.

Docs/03 §1-10 ga aniq mos:
  1. Input: rasm yoki PDF sahifa
  2. Normalize: grayscale, blur, threshold
  3. QR decode → uuid
  4. Find anchors
  5. Warp perspective
  6. Load grid (layout.py)
  7. Read bubbles
  8. Decide per question
  9. Return result
 10. Debug (ixtiyoriy)
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

log = logging.getLogger(__name__)


# ─── Natija tuzilmasi ──────────────────────────────────────────────────────────

@dataclass
class PipelineResult:
    """OMR pipeline natijasi."""
    titul_uuid: Optional[str]           # QR dan o'qilgan uuid
    detected: dict[str, Optional[str]]  # {"1": "A", "2": None, ...}
    bubble_data: dict[str, dict]        # to'liq fill_ratio/flag/conf ma'lumoti
    needs_review: bool
    warped: Optional[np.ndarray] = field(default=None, repr=False)
    anchor_centers: Optional[np.ndarray] = field(default=None, repr=False)
    error: Optional[str] = None


# ─── Yordamchi: PDF sahifalarini rasmga aylantirish ──────────────────────────

def pdf_to_images(pdf_path: str | Path, dpi: int = 200) -> list[np.ndarray]:
    """
    PDF faylni rasmlar ro'yxatiga aylantiradi (har sahifa).

    Args:
        pdf_path: PDF fayl yo'li.
        dpi:      Rasterizatsiya DPI.

    Returns:
        Grayscale numpy array'lar ro'yxati.
    """
    import fitz  # PyMuPDF

    doc = fitz.open(str(pdf_path))
    images: list[np.ndarray] = []
    mat = fitz.Matrix(dpi / 72, dpi / 72)

    for page in doc:
        pix = page.get_pixmap(matrix=mat)
        data = np.frombuffer(pix.samples, dtype=np.uint8)
        if pix.n == 1:
            img = data.reshape(pix.h, pix.w)
        elif pix.n == 3:
            img = cv2.cvtColor(
                data.reshape(pix.h, pix.w, 3), cv2.COLOR_RGB2GRAY
            )
        elif pix.n == 4:
            img = cv2.cvtColor(
                data.reshape(pix.h, pix.w, 4), cv2.COLOR_RGBA2GRAY
            )
        else:
            img = cv2.cvtColor(
                data.reshape(pix.h, pix.w, pix.n), cv2.COLOR_BGR2GRAY
            )
        images.append(img)

    doc.close()
    return images


def load_image(file_path: str | Path) -> list[np.ndarray]:
    """
    Rasm yoki PDF faylni yuklaydi.

    Returns:
        Grayscale numpy array'lar ro'yxati (PDF: har sahifa, rasm: 1 ta).
    """
    fp = Path(file_path)
    ext = fp.suffix.lower()

    if ext == ".pdf":
        return pdf_to_images(fp)
    else:
        img = cv2.imread(str(fp))
        if img is None:
            raise ValueError(f"Rasm o'qilmadi: {fp}")
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return [gray]


def preprocess(gray: np.ndarray) -> np.ndarray:
    """
    Grayscale → blur → Otsu threshold (to'ldirilgan = OQ).

    Returns:
        Binary rasm (0/255, filled=white).
    """
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    # THRESH_BINARY_INV: qora doira → oq (filled=white)
    _, binary = cv2.threshold(
        blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )
    return binary


# ─── Asosiy pipeline ───────────────────────────────────────────────────────────

def run_single(
    gray: np.ndarray,
    *,
    fill_min: float = 0.35,
    fill_margin: float = 0.15,
    warp_w: int = 1449,
    warp_h: int = 2134,
    omr_dpi: int = 200,
    qcount: Optional[int] = None,  # QR'dan ma'lum bo'lmasa
    vcount: int = 4,
    omr_debug: bool = False,
    debug_out_path: Optional[Path] = None,
) -> PipelineResult:
    """
    Bitta rasm (grayscale) uchun to'liq OMR pipeline'ni ishlatadi.

    Args:
        gray:           Grayscale rasm.
        fill_min:       Bo'sh doira chegarasi.
        fill_margin:    Ikkilanish chegarasi.
        warp_w/h:       Warp natijasi o'lchami.
        omr_dpi:        Grid hisobi uchun DPI.
        qcount:         Savol soni (None: DB'dan olinadi).
        vcount:         Variant soni.
        omr_debug:      Debug rasm saqlash.
        debug_out_path: Debug rasm yo'li.

    Returns:
        PipelineResult.
    """
    from app.omr.qr import read_qr
    from app.omr.anchors import find_anchors, warp_perspective
    from app.omr.bubbles import read_all_bubbles
    from app.omr.layout import omr_grid_px, warped_size_px

    # 2. QR o'qish
    titul_uuid = read_qr(gray)

    # 3. Anchorlarni topish
    anchor_centers = find_anchors(gray)

    if anchor_centers is None:
        return PipelineResult(
            titul_uuid=titul_uuid,
            detected={},
            bubble_data={},
            needs_review=True,
            anchor_centers=None,
            error="Anchor topilmadi",
        )

    # 4. Perspektiva to'g'rilash
    #
    # MUHIM: warp o'lchami grid bilan AYNAN bir koordinata fazosida bo'lishi shart.
    # omr_grid_px() doiralarni anchor-markazlari to'rtburchagi (foydali maydon)
    # ichida hisoblaydi, ya'ni warp anchor markazlarini (0,0)-(W,H) ga keltirishi
    # kerak, bunda (W,H) = warped_size_px(omr_dpi). Aks holda doiralar noto'g'ri
    # joydan o'qiladi (bo'sh<->to'ldirilgan teskari bo'lib ketadi).
    #
    # Shu sababli warp o'lchamini layout'dan hisoblaymiz — tashqaridan kelgan
    # warp_w/warp_h (config) bilan grid orasida nomuvofiqlik bo'lishining oldini
    # oladi.
    grid_w, grid_h = warped_size_px(omr_dpi)
    if (warp_w, warp_h) != (grid_w, grid_h):
        log.warning(
            "warp_w/warp_h (%dx%d) grid fazosiga (%dx%d) mos emas — "
            "layout'dan hisoblangan o'lcham ishlatiladi.",
            warp_w, warp_h, grid_w, grid_h,
        )
    warped_gray = warp_perspective(gray, anchor_centers, grid_w, grid_h)

    # 5. Binary (to'ldirilgan = oq)
    warped_bin = preprocess(warped_gray)

    # 6. Grid (qcount ma'lum bo'lishi kerak)
    if qcount is None:
        # Barcha mumkin bo'lgan layout'larni sinab ko'ramiz (40, 50, 90)
        # Amalda qcount titul→test dan olinadi; bu yerda default 40
        qcount = 40
        log.warning("qcount berilmagan, 40 qabul qilindi")

    grid = omr_grid_px(qcount, dpi=omr_dpi, vcount=vcount)

    # 7. Doiralarni o'qish
    bubble_data = read_all_bubbles(warped_bin, grid, fill_min, fill_margin)

    # 8. Detected dict (faqat javob)
    detected: dict[str, Optional[str]] = {
        q: bd["answer"] for q, bd in bubble_data.items()
    }

    # 9. needs_review: birorta ambiguous yoki blank flag bo'lsa
    needs_review = any(
        bd["flag"] in ("ambiguous",) for bd in bubble_data.values()
    )

    # 10. Debug
    if omr_debug and debug_out_path:
        from app.omr.debug import annotate
        annotate(warped_gray, grid, bubble_data, anchor_centers, debug_out_path)

    return PipelineResult(
        titul_uuid=titul_uuid,
        detected=detected,
        bubble_data=bubble_data,
        needs_review=needs_review,
        warped=warped_gray,
        anchor_centers=anchor_centers,
    )


def read_qr_from_file(file_path: str | Path) -> Optional[str]:
    """
    Faqat QR kodni o'qiydi (anchor/warp/bubble QILINMAYDI).

    Bu funksiya tasks.py'da DB so'rovidan oldin titul UUID'ni olish uchun
    ishlatiladi, shunda to'liq pipeline to'g'ri qcount/vcount bilan chaqiriladi.

    Args:
        file_path: Rasm yoki PDF fayl yo'li.

    Returns:
        Titul UUID string yoki None (QR topilmasa).
    """
    from app.omr.qr import read_qr

    images = load_image(file_path)
    if not images:
        log.warning("read_qr_from_file: fayl bo'sh yoki o'qilmadi: %s", file_path)
        return None

    # Faqat birinchi sahifada QR bo'lishi kutiladi
    titul_uuid = read_qr(images[0])
    if titul_uuid is None:
        log.warning("read_qr_from_file: QR topilmadi: %s", file_path)
    return titul_uuid


def run(
    file_path: str | Path,
    *,
    fill_min: float = 0.35,
    fill_margin: float = 0.15,
    warp_w: int = 1449,
    warp_h: int = 2134,
    omr_dpi: int = 200,
    qcount: Optional[int] = None,
    vcount: int = 4,
    omr_debug: bool = False,
    debug_out_dir: Optional[Path] = None,
) -> list[PipelineResult]:
    """
    Fayl (rasm yoki PDF) uchun OMR pipeline (har sahifa).

    Returns:
        PipelineResult ro'yxati (PDF → N sahifa, rasm → 1 ta).
    """
    images = load_image(file_path)
    results: list[PipelineResult] = []

    for idx, gray in enumerate(images):
        if omr_debug and debug_out_dir:
            stem = Path(file_path).stem
            dbg_path = debug_out_dir / f"{stem}_page{idx}_debug.jpg"
        else:
            dbg_path = None

        res = run_single(
            gray,
            fill_min=fill_min,
            fill_margin=fill_margin,
            warp_w=warp_w,
            warp_h=warp_h,
            omr_dpi=omr_dpi,
            qcount=qcount,
            vcount=vcount,
            omr_debug=omr_debug,
            debug_out_path=dbg_path,
        )
        results.append(res)

    return results

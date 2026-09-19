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

Resurs himoyasi (weaknesses.md №14, №23):
  - PDF'dan faqat `max_pages` ta sahifa rasterizatsiya qilinadi (standart 1).
  - Rasm DEKODDAN OLDIN o'lchami tekshiriladi (`MAX_IMAGE_PIXELS`) —
    dekompressiya bombasi worker'ni OOM qilmasin.
  - `run(images=...)` bir marta yuklangan kadrlarni qayta ishlatadi;
    fayl ikki marta o'qilmaydi.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

log = logging.getLogger(__name__)

# Dekoddan keyin xotirada bitta kadr uchun ruxsat etilgan maksimal piksel soni.
# 30 MP ≈ 30 MB grayscale; undan kattasi deyarli har doim dekompressiya bombasi
# yoki noto'g'ri fayl (12 MP telefon surati bemalol sig'adi).
MAX_IMAGE_PIXELS = 30_000_000

# PDF'dan nechta sahifa o'qiladi (standart). Titul bir varaqli.
DEFAULT_MAX_PAGES = 1

# OpenCV o'qiy olmaydigan, lekin Telegram yuboradigan formatlar.
UNSUPPORTED_SUFFIXES = {".heic", ".heif"}


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

def _pdf_to_images(
    pdf_path: str | Path,
    dpi: int = 200,
    max_pages: Optional[int] = DEFAULT_MAX_PAGES,
) -> tuple[list[np.ndarray], int]:
    """
    PDF faylni rasmlar ro'yxatiga aylantiradi (faqat `max_pages` ta sahifa).

    Ilgari BARCHA sahifalar rasterizatsiya qilinardi — yuzlab sahifali PDF
    worker'ni OOM qilardi (weaknesses.md №14).

    Returns:
        (grayscale rasmlar ro'yxati, PDF'dagi umumiy sahifalar soni).
    """
    import fitz  # PyMuPDF

    doc = fitz.open(str(pdf_path))
    try:
        total_pages = doc.page_count
        images: list[np.ndarray] = []
        mat = fitz.Matrix(dpi / 72, dpi / 72)

        for idx, page in enumerate(doc):
            if max_pages is not None and idx >= max_pages:
                break

            rect = page.rect
            px_w = int(rect.width * dpi / 72)
            px_h = int(rect.height * dpi / 72)
            if px_w * px_h > MAX_IMAGE_PIXELS:
                raise ValueError(
                    "PDF sahifasi juda katta "
                    f"({px_w}x{px_h} px). Kichikroq fayl yuboring."
                )

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

        if max_pages is not None and total_pages > max_pages:
            log.warning(
                "PDF'da %d sahifa bor, faqat %d tasi tekshiriladi: %s",
                total_pages, max_pages, pdf_path,
            )

        return images, total_pages
    finally:
        doc.close()


def pdf_to_images(
    pdf_path: str | Path,
    dpi: int = 200,
    max_pages: Optional[int] = DEFAULT_MAX_PAGES,
) -> list[np.ndarray]:
    """PDF → grayscale rasmlar (faqat birinchi `max_pages` sahifa)."""
    return _pdf_to_images(pdf_path, dpi=dpi, max_pages=max_pages)[0]


def _check_image_size(fp: Path) -> None:
    """
    Rasm o'lchamini DEKODDAN OLDIN tekshiradi (PIL faqat header o'qiydi).

    Raises:
        ValueError: rasm `MAX_IMAGE_PIXELS` dan katta bo'lsa.
    """
    try:
        from PIL import Image
    except ImportError:  # pragma: no cover — Pillow WeasyPrint bilan keladi
        log.warning("Pillow yo'q — rasm o'lchami tekshirilmadi: %s", fp)
        return

    # PIL ning o'z bomba himoyasi ham yoqilsin.
    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

    try:
        with Image.open(fp) as im:
            w, h = im.size
    except Exception as exc:
        raise ValueError(f"Rasm o'qilmadi: {fp.name}") from exc

    if w * h > MAX_IMAGE_PIXELS:
        raise ValueError(
            f"Rasm juda katta ({w}x{h} px). Kichikroq surat yuboring."
        )


def load_pages(
    file_path: str | Path,
    *,
    dpi: int = 200,
    max_pages: Optional[int] = DEFAULT_MAX_PAGES,
) -> tuple[list[np.ndarray], int]:
    """
    Rasm yoki PDF faylni yuklaydi.

    Returns:
        (grayscale kadrlar ro'yxati, manbadagi umumiy sahifalar soni).
        Rasm uchun umumiy sahifalar soni doim 1.
    """
    fp = Path(file_path)
    ext = fp.suffix.lower()

    if ext == ".pdf":
        return _pdf_to_images(fp, dpi=dpi, max_pages=max_pages)

    if ext in UNSUPPORTED_SUFFIXES:
        # OpenCV HEIC/HEIF ni o'qiy olmaydi — bot uni qabul qilmaydi, lekin
        # ichki API orqali kelib qolsa aniq xato bo'lsin (weaknesses.md №30).
        raise ValueError(
            "HEIC/HEIF format qo'llanmaydi. Rasmni JPEG yoki PNG ko'rinishida yuboring."
        )

    _check_image_size(fp)

    img = cv2.imread(str(fp))
    if img is None:
        raise ValueError(f"Rasm o'qilmadi: {fp.name}")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return [gray], 1


def load_image(
    file_path: str | Path,
    *,
    dpi: int = 200,
    max_pages: Optional[int] = DEFAULT_MAX_PAGES,
) -> list[np.ndarray]:
    """
    Rasm yoki PDF faylni yuklaydi (faqat kadrlar).

    Returns:
        Grayscale numpy array'lar ro'yxati.
    """
    return load_pages(file_path, dpi=dpi, max_pages=max_pages)[0]


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


# ─── Orientatsiya ──────────────────────────────────────────────────────────────

# Shablonda QR YUQORI-O'NG burchakda (pdf/templates/base.html: top+right).
# Warp fazosida uning markazi shu kvadrantda bo'lishi kutiladi.
def _qr_quadrant(
    qr_center: tuple[float, float],
    anchor_centers: np.ndarray,
    w: int,
    h: int,
) -> tuple[str, tuple[float, float]]:
    """
    QR markazini warp fazosiga o'tkazib, qaysi kvadrantda ekanini aytadi.

    Returns:
        ("TR" | "TL" | "BR" | "BL", (x, y)) — warp fazosidagi koordinata.
    """
    dst = np.array(
        [[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], dtype="float32"
    )
    m = cv2.getPerspectiveTransform(anchor_centers.astype("float32"), dst)
    pt = np.array([[[float(qr_center[0]), float(qr_center[1])]]], dtype="float32")
    x, y = cv2.perspectiveTransform(pt, m)[0][0]

    vert = "T" if y < h / 2 else "B"
    horiz = "L" if x < w / 2 else "R"
    return f"{vert}{horiz}", (float(x), float(y))


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
    from app.omr.qr import read_qr_located
    from app.omr.anchors import find_anchors, warp_perspective
    from app.omr.bubbles import read_all_bubbles
    from app.omr.layout import omr_grid_px, warped_size_px

    # 2. QR o'qish (markazi bilan — orientatsiya uchun kerak)
    titul_uuid, qr_center = read_qr_located(gray)

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

    # 4a. Orientatsiya (weaknesses.md №13).
    # `order_points` faqat rasm burchaklarini tartiblaydi — varaq 180° burilgan
    # bo'lsa TL↔BR almashadi va grid oynadek buriladi, natijada HAMMA javob
    # "xato" bo'lib, buni hech narsa bildirmasdi. QR fizik yo'nalishni beradi.
    needs_review_orientation = False
    if qr_center is not None:
        quadrant, warped_xy = _qr_quadrant(qr_center, anchor_centers, grid_w, grid_h)
        if quadrant == "BL":
            log.info("Varaq 180° burilgan — anchorlar almashtirildi (QR: %s)", warped_xy)
            # [TL,TR,BR,BL] → [BR,BL,TL,TR]: to'liq 180° almashish.
            anchor_centers = np.roll(anchor_centers, 2, axis=0)
        elif quadrant != "TR":
            return PipelineResult(
                titul_uuid=titul_uuid,
                detected={},
                bubble_data={},
                needs_review=True,
                anchor_centers=anchor_centers,
                error="Varaq yon tomonga burilgan",
            )
    else:
        # QR o'qilmasa yo'nalishni aniqlab bo'lmaydi — natija shubhali.
        log.warning("QR topilmadi — varaq yo'nalishi tekshirilmadi")
        needs_review_orientation = True

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

    # 9. needs_review: birorta ambiguous flag yoki yo'nalish tekshirilmagan bo'lsa
    needs_review = needs_review_orientation or any(
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

    Eslatma: `omr_task` endi faylni bir marta yuklab `read_qr(images[0])` ni
    o'zi chaqiradi (T-18). Bu funksiya ichki API va skriptlar uchun qoldi.

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
    file_path: str | Path | None = None,
    *,
    images: Optional[list[np.ndarray]] = None,
    fill_min: float = 0.35,
    fill_margin: float = 0.15,
    warp_w: int = 1449,
    warp_h: int = 2134,
    omr_dpi: int = 200,
    qcount: Optional[int] = None,
    vcount: int = 4,
    omr_debug: bool = False,
    debug_out_dir: Optional[Path] = None,
    max_pages: Optional[int] = DEFAULT_MAX_PAGES,
) -> list[PipelineResult]:
    """
    Fayl (rasm yoki PDF) uchun OMR pipeline.

    Args:
        file_path: Manba fayl. `images` berilsa faqat debug nomi uchun kerak.
        images:    Oldindan yuklangan kadrlar — fayl ikki marta o'qilmasin
                   (weaknesses.md №14). `None` bo'lsa fayldan yuklanadi.
        max_pages: PDF'dan nechta sahifa o'qiladi.

    Returns:
        PipelineResult ro'yxati.
    """
    if images is None:
        if file_path is None:
            raise ValueError("run(): `file_path` yoki `images` berilishi shart")
        images = load_image(file_path, dpi=omr_dpi, max_pages=max_pages)

    results: list[PipelineResult] = []
    stem = Path(file_path).stem if file_path else "scan"

    for idx, gray in enumerate(images):
        if omr_debug and debug_out_dir:
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

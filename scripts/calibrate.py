"""
scripts/calibrate.py — LAYOUTS_MM ni vizual tekshirish uchun yordamchi skript.

Foydalanish:
    python scripts/calibrate.py --qcount 40 [--dpi 200] [--pdf path/to/titul.pdf]

Nima qiladi:
  1. Agar --pdf berilsa: PDF 0-sahifasini rastrga aylantiradi
     Aks holda: bo'sh titul PDF ni generatsiya qiladi (WeasyPrint kerak)
  2. omr_grid_px() koordinatalarini rasm ustiga chizadi:
     - Ko'k doira: doira o'rni
     - Yashil kvadrat: anchor o'rni
  3. Annotatsiyalangan rasmni saqlab, yo'lini chiqaradi

Natijani ko'rib, agar doiralar varaqda noto'g'ri joylashgan bo'lsa,
app/omr/layout.py dagi LAYOUTS_MM ni sozlang.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

# Loyiha ildizini sys.path ga qo'shish
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import cv2
import numpy as np


def rasterize_pdf(pdf_path: str, dpi: int) -> np.ndarray:
    """PDF birinchi sahifasini grayscale np.ndarray ga aylantirish."""
    import fitz
    doc = fitz.open(pdf_path)
    page = doc[0]
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    data = np.frombuffer(pix.samples, dtype=np.uint8)
    if pix.n == 3:
        img = cv2.cvtColor(data.reshape(pix.h, pix.w, 3), cv2.COLOR_RGB2BGR)
    elif pix.n == 4:
        img = cv2.cvtColor(data.reshape(pix.h, pix.w, 4), cv2.COLOR_RGBA2BGR)
    else:
        img = data.reshape(pix.h, pix.w)
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    doc.close()
    return img


def generate_blank_titul(qcount: int, dpi: int) -> str:
    """
    Bo'sh titul PDF generatsiya qilib vaqtincha faylga saqlash.
    Placeholder ma'lumotlar bilan.
    """
    from app.pdf.qrgen import make_qr_data_uri
    from app.pdf.render import render_titul_pdf

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.close()

    render_titul_pdf(
        titul_uuid="00000000-0000-0000-0000-000000000000",
        test_title="KALIBRLASH TESTI",
        group_name="Test Guruhi",
        student_name="Test O'quvchi",
        question_count=qcount,
        variant_count=4,
        qr_data_uri=make_qr_data_uri("00000000-0000-0000-0000-000000000000"),
        out_path=tmp.name,
        bot_username="calibrate",
    )
    return tmp.name


def annotate_calibration(
    img: np.ndarray,
    qcount: int,
    dpi: int,
) -> np.ndarray:
    """
    Rasmga anchor va bubble doiralarini chizish.
    Rasm koordinatalari: PDF rasm (dpi bo'yicha).
    Grid koordinatalari warp-space (anchor=0,0 dan).
    """
    from app.omr.layout import (
        ANCHOR_CENTER_OFFSET_MM,
        PAGE_H_MM,
        PAGE_W_MM,
        omr_grid_px,
    )

    k = dpi / 25.4

    # ─ Anchor markazlari (PDF koordinatada) ──────────────────────────────────
    off = ANCHOR_CENTER_OFFSET_MM
    anchor_centers_mm = [
        (off, off),                        # TL
        (PAGE_W_MM - off, off),            # TR
        (PAGE_W_MM - off, PAGE_H_MM - off),# BR
        (off, PAGE_H_MM - off),            # BL
    ]
    for ax_mm, ay_mm in anchor_centers_mm:
        ax, ay = int(ax_mm * k), int(ay_mm * k)
        cv2.rectangle(img, (ax - 15, ay - 15), (ax + 15, ay + 15), (0, 200, 0), 2)
        cv2.circle(img, (ax, ay), 4, (0, 200, 0), -1)

    # ─ Bubble markazlari (warp-space) — sahifa offset bilan ────────────────
    grid = omr_grid_px(qcount, dpi=dpi)
    anchor_offset_px_x = int(off * k)
    anchor_offset_px_y = int(off * k)

    for cell in grid:
        # Warp koordinatasi → PDF koordinatasi
        px = int(cell["cx"]) + anchor_offset_px_x
        py = int(cell["cy"]) + anchor_offset_px_y
        r = max(3, int(cell["r"]))
        cv2.circle(img, (px, py), r, (200, 80, 0), 1)
        cv2.circle(img, (px, py), 2, (200, 80, 0), -1)

    # ─ Sarlavha ─────────────────────────────────────────────────────────────
    cv2.putText(
        img,
        f"KALIBRLASH - {qcount} SAVOL ({dpi} DPI)",
        (30, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (0, 0, 200),
        2,
        cv2.LINE_AA,
    )

    return img


def main() -> None:
    parser = argparse.ArgumentParser(
        description="OMR layout kalibrlash vositasi"
    )
    parser.add_argument(
        "--qcount",
        type=int,
        choices=[40, 50, 90],
        default=40,
        help="Savol soni",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=200,
        help="Rasterizatsiya DPI (default: 200)",
    )
    parser.add_argument(
        "--pdf",
        type=str,
        default=None,
        help="Mavjud titul PDF yo'li (yo'q bo'lsa avtomatik generatsiya)",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Natija rasm yo'li (default: calibration_<qcount>.png)",
    )
    args = parser.parse_args()

    print(f"Kalibrlash: qcount={args.qcount}, dpi={args.dpi}")

    # PDF manba
    if args.pdf:
        if not Path(args.pdf).exists():
            print(f"Xato: {args.pdf} topilmadi")
            sys.exit(1)
        pdf_path = args.pdf
        tmp_pdf = None
        print(f"PDF: {pdf_path}")
    else:
        print("Bo'sh titul PDF generatsiya qilinmoqda...")
        try:
            pdf_path = generate_blank_titul(args.qcount, args.dpi)
            tmp_pdf = pdf_path
            print(f"PDF yaratildi: {pdf_path}")
        except Exception as e:
            print(f"PDF generatsiya xatosi: {e}")
            print("WeasyPrint o'rnatilganligini tekshiring.")
            sys.exit(1)

    # PDF → rasm
    print("Rasterizatsiya...")
    try:
        img = rasterize_pdf(pdf_path, args.dpi)
    except Exception as e:
        print(f"Rasterizatsiya xatosi: {e}")
        sys.exit(1)
    finally:
        if tmp_pdf:
            os.unlink(tmp_pdf)

    # Annotatsiya
    print("Grid ustiga chizilmoqda...")
    annotated = annotate_calibration(img, args.qcount, args.dpi)

    # Saqlash
    out_path = args.out or f"calibration_{args.qcount}.png"
    cv2.imwrite(out_path, annotated)
    print(f"\n✅ Annotatsiyalangan rasm saqlandi: {out_path}")
    print()
    print("Ko'rsatmalar:")
    print("  🟢 Yashil kvadratlar = anchor markazlari")
    print("  🔵 Ko'k doiralar = bubble markazlari")
    print()
    print("Agar doiralar titul varaqidagi doiralar bilan mos kelmasa,")
    print("app/omr/layout.py dagi LAYOUTS_MM ni sozlang:")
    print("  - x0, y0: blok boshlang'ich koordinatalari (mm)")
    print("  - dx, dy: variantlar va savollar oralig'i (mm)")
    print("  - d: doira diametri (mm)")


if __name__ == "__main__":
    main()

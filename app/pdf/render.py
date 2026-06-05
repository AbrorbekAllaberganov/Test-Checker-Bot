"""
app/pdf/render.py — HTML shablon → PDF (WeasyPrint + Jinja2).

Yagona haqiqat manbasi:
  build_bubble_positions()  → doira joylari (PDF uchun)
  block_labels()            → blok sarlavhalari
  omr_grid_px()             → OMR pipeline koordinatalari

Bu fayl faqat PDF rendering bilan shug'ullanadi.
"""
from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

from app.omr.layout import ANCHOR_CENTER_OFFSET_MM, LAYOUTS_MM, block_labels, build_bubble_positions

log = logging.getLogger(__name__)

# Shablon papkasi
_TEMPLATE_DIR = Path(__file__).parent / "templates"

_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)


def _build_qnums(qcount: int) -> list[dict]:
    """
    Savol raqamlari joylashuvi (HTML uchun).
    Har savol birinchi doira ustunidan chapda.
    """
    L = LAYOUTS_MM[qcount]
    qnums: list[dict] = []
    for b in L["blocks"]:
        for i in range(b["count"]):
            qnums.append({
                "n": b["start"] + i,
                # savol raqami birinchi doiradan chap tomonda
                "x": round(b["x0"] - 7, 2),
                "y": round(b["y0"] + i * b["dy"] + (b["d"] - 3) / 2, 2),
            })
    return qnums


def render_titul_pdf(
    *,
    titul_uuid: str,
    test_title: str,
    group_name: str,
    student_name: str,
    question_count: int,
    variant_count: int,
    qr_data_uri: str,
    out_path: str | Path,
    bot_username: str = "omr_test_bot",
) -> Path:
    """
    Titul PDF ni yaratib `out_path` ga saqlaydi.

    Args:
        titul_uuid:     Titul UUID (QR ichida va footer'da).
        test_title:     Test nomi.
        group_name:     Guruh nomi.
        student_name:   O'quvchi F.I.Sh.
        question_count: 40 | 50 | 90.
        variant_count:  2-5.
        qr_data_uri:    base64 PNG data URI.
        out_path:       Saqlanadigan fayl yo'li.
        bot_username:   Bot username (header uchun).

    Returns:
        Yaratilgan fayl yo'li.
    """
    bubbles = build_bubble_positions(question_count, variant_count)
    blabels = block_labels(question_count)
    qnums = _build_qnums(question_count)

    template_name = f"titul_{question_count}.html"
    tpl = _jinja_env.get_template(template_name)

    html_str = tpl.render(
        titul_uuid=titul_uuid,
        test_title=test_title,
        group_name=group_name,
        student_name=student_name,
        question_count=question_count,
        qr_data_uri=qr_data_uri,
        bubbles=bubbles,
        block_labels=blabels,
        qnums=qnums,
        bot_username=bot_username,
    )

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    HTML(string=html_str, base_url=str(_TEMPLATE_DIR)).write_pdf(str(out_path))
    log.info("PDF yaratildi: %s", out_path)
    return out_path

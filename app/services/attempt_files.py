"""
app/services/attempt_files.py — Skan fayllarini (surat, OMR annotatsiyasi)
xavfsiz berish.

Ilgari bu fayllar `/static/uploads` va `/static/debug` orqali
autentifikatsiyasiz berilardi (weaknesses.md №4). Endi Mini App
(`/api/web/attempts/{id}/file/{kind}`) va admin panel
(`/api/admin/scans/{id}/file/{kind}`) egalik/rol tekshiruvidan keyin shu
moduldagi funksiyalar bilan faylni qaytaradi.
"""
from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import Literal, Optional

from fastapi.responses import FileResponse

from app.core.config import get_settings

log = logging.getLogger(__name__)

FileKind = Literal["source", "debug"]


def allowed_file_roots() -> tuple[Path, ...]:
    """Fayl berish endpointlari faqat shu papkalardagi fayllarni qaytaradi."""
    settings = get_settings()
    return (
        settings.temp_dir.resolve(),          # skan suratlari (source_file)
        settings.debug_output_dir.resolve(),  # OMR annotatsiyasi (debug_file)
    )


def resolve_attempt_file(filepath: Optional[str]) -> Optional[Path]:
    """
    Bazadagi yo'lni tekshirib, xavfsiz bo'lsa qaytaradi.

    Yo'l ruxsat etilgan papkalardan tashqarida bo'lsa (path traversal yoki
    buzilgan yozuv) yoki fayl yo'q bo'lsa — None.
    """
    if not filepath:
        return None
    try:
        path = Path(filepath).resolve()
    except (OSError, RuntimeError):
        return None
    if not path.is_file():
        return None
    if not any(path.is_relative_to(root) for root in allowed_file_roots()):
        log.warning("Attempt fayli ruxsat etilgan papkalardan tashqarida: %s", filepath)
        return None
    return path


def attempt_file_path(attempt, kind: FileKind) -> Optional[Path]:
    """Attempt + tur → tekshirilgan fayl yo'li (yo'q bo'lsa None)."""
    raw = attempt.source_file if kind == "source" else attempt.debug_file
    return resolve_attempt_file(raw)


def file_response_for(path: Path) -> FileResponse:
    """Rasm/PDF uchun FileResponse. Kesh `private` — faqat shu brauzerda."""
    media_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    return FileResponse(
        path,
        media_type=media_type,
        headers={"Cache-Control": "private, max-age=300"},
    )

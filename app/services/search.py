"""
app/services/search.py — Qidiruv matnini SQL LIKE uchun tayyorlash.

`%` va `_` — LIKE ning maxsus belgilari. Ular ekranlanmasa foydalanuvchi
kiritgan `"100%"` butun jadvalni qaytaradi, `"_"` esa istalgan bitta belgiga
mos keladi (weaknesses.md №35). Bu SQL in'ektsiya emas — parametrlar bog'langan —
lekin natija noto'g'ri va katta jadvalda qimmatga tushadi.
"""
from __future__ import annotations

# `ilike(..., escape=LIKE_ESCAPE)` bilan birga ishlatiladi.
LIKE_ESCAPE = "\\"


def like_pattern(term: str) -> str:
    """
    Foydalanuvchi matnini `%term%` shabloniga aylantiradi (ekranlangan).

    Args:
        term: Qidiruv matni.

    Returns:
        `ILIKE` uchun tayyor shablon. `escape="\\\\"` argumenti bilan
        ishlatilishi SHART.
    """
    t = (
        term.strip()
        .replace(LIKE_ESCAPE, LIKE_ESCAPE * 2)
        .replace("%", LIKE_ESCAPE + "%")
        .replace("_", LIKE_ESCAPE + "_")
    )
    return f"%{t}%"

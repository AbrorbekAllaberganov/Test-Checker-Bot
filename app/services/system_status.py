"""
app/services/system_status.py — Redis / Celery / DB sog'lig'ini tekshirish.

Celery inspect chaqiruvlari bloklovchi (sync) va sekin bo'lishi mumkin, shu
sababli ular `asyncio.to_thread` orqali ishlatiladi va qat'iy timeout bilan
cheklanadi — admin paneli ochilmay qolmasligi uchun.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings

log = logging.getLogger(__name__)

# Celery inspect uchun bitta so'rov oynasi (sekund).
#
# DIQQAT: `inspect()` har doim to'liq shu vaqtni kutadi (worker darrov javob
# bersa ham), va biz 4 ta chaqiruv qilamiz (ping/active/reserved/stats) —
# ya'ni jami ~4 × INSPECT_TIMEOUT. Tashqi timeout shuni hisobga oladi.
INSPECT_TIMEOUT = 1.0
_INSPECT_CALLS = 4
# Bloklovchi inspect uchun umumiy chegara + kichik zaxira.
INSPECT_TOTAL_TIMEOUT = INSPECT_TIMEOUT * _INSPECT_CALLS + 2.0


@dataclass
class ComponentHealth:
    name: str
    status: str  # "up" | "down" | "degraded" | "unknown"
    detail: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)


async def check_database(db: AsyncSession) -> ComponentHealth:
    try:
        await db.execute(text("SELECT 1"))
        size = (
            await db.execute(text("SELECT pg_database_size(current_database())"))
        ).scalar()
        return ComponentHealth(
            name="postgres",
            status="up",
            detail="Ulanish bor",
            metrics={"size_bytes": int(size or 0)},
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("Postgres health tekshiruvi muvaffaqiyatsiz: %s", exc)
        return ComponentHealth(name="postgres", status="down", detail=str(exc))


async def check_redis() -> ComponentHealth:
    """Redis PING + navbat uzunligi (`default` queue)."""
    settings = get_settings()
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(settings.redis_url, socket_timeout=INSPECT_TIMEOUT)
        try:
            await client.ping()
            info = await client.info(section="memory")
            # Celery navbati Redis'da oddiy list sifatida turadi.
            queue_len = await client.llen("default")
            return ComponentHealth(
                name="redis",
                status="up",
                detail="PONG",
                metrics={
                    "queue_length": int(queue_len or 0),
                    "used_memory_bytes": int(info.get("used_memory", 0)),
                    "used_memory_human": info.get("used_memory_human", ""),
                },
            )
        finally:
            await client.aclose()
    except Exception as exc:  # noqa: BLE001
        log.warning("Redis health tekshiruvi muvaffaqiyatsiz: %s", exc)
        return ComponentHealth(name="redis", status="down", detail=str(exc))


def _inspect_workers() -> dict[str, Any]:
    """Bloklovchi Celery inspect — alohida thread'da chaqiriladi."""
    from app.worker.celery_app import celery_app

    inspector = celery_app.control.inspect(timeout=INSPECT_TIMEOUT)
    ping = inspector.ping() or {}
    active = inspector.active() or {}
    reserved = inspector.reserved() or {}
    stats = inspector.stats() or {}

    workers: list[dict[str, Any]] = []
    for name in sorted(ping.keys()):
        worker_stats = stats.get(name, {})
        workers.append(
            {
                "name": name,
                "status": "up",
                "active_tasks": len(active.get(name, [])),
                "reserved_tasks": len(reserved.get(name, [])),
                "concurrency": (worker_stats.get("pool") or {}).get("max-concurrency"),
                "total_completed": sum((worker_stats.get("total") or {}).values()),
                "uptime_seconds": worker_stats.get("uptime"),
            }
        )

    return {
        "workers": workers,
        "active_total": sum(len(v) for v in active.values()),
        "reserved_total": sum(len(v) for v in reserved.values()),
    }


async def check_celery() -> ComponentHealth:
    try:
        data = await asyncio.wait_for(
            asyncio.to_thread(_inspect_workers), timeout=INSPECT_TOTAL_TIMEOUT
        )
    except Exception as exc:  # noqa: BLE001 — timeout ham shu yerga tushadi
        log.warning("Celery inspect muvaffaqiyatsiz: %s", exc)
        return ComponentHealth(
            name="celery",
            status="unknown",
            detail="Worker'lar javob bermadi (inspect timeout)",
            metrics={"workers": [], "active_total": 0, "reserved_total": 0},
        )

    worker_count = len(data["workers"])
    return ComponentHealth(
        name="celery",
        status="up" if worker_count else "down",
        detail=f"{worker_count} ta worker javob berdi",
        metrics=data,
    )


async def full_status(db: AsyncSession) -> dict[str, Any]:
    """Uchala komponentni parallel tekshiradi."""
    database, redis_h, celery_h = await asyncio.gather(
        check_database(db), check_redis(), check_celery()
    )
    components = [database, redis_h, celery_h]
    overall = (
        "up"
        if all(c.status == "up" for c in components)
        else ("down" if any(c.status == "down" for c in components) else "degraded")
    )
    return {
        "overall": overall,
        "components": [
            {
                "name": c.name,
                "status": c.status,
                "detail": c.detail,
                "metrics": c.metrics,
            }
            for c in components
        ],
    }

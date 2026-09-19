"""
app/worker/celery_app.py — Celery application instance.
"""
from __future__ import annotations

from celery import Celery
from celery.signals import worker_process_init

from app.core.config import get_settings

settings = get_settings()

# Result backend YO'Q (weaknesses.md №32): natijalar hech qayerda o'qilmaydi
# (`AsyncResult` chaqirig'i kodda yo'q), lekin Redis'da 24 soat yotardi.
# `task_id` faqat log uchun qoladi — u broker'ga bog'liq emas.
celery_app = Celery(
    "omr_worker",
    broker=settings.redis_url,
    include=["app.worker.tasks", "app.worker.broadcast_tasks"],
)

celery_app.conf.update(
    task_default_queue="default",
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone=settings.app_timezone,
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Natija saqlanmaydi (backend ham yo'q).
    task_ignore_result=True,
    # Vaqt limitlari (weaknesses.md №14): `acks_late=True` bilan osilgan task
    # visibility timeout (~1 soat) dan keyin QAYTA yetkazilardi — bir varaq
    # ikki marta baholanardi. Endi task 4 daqiqada `SoftTimeLimitExceeded`
    # oladi va o'zini toza yakunlaydi; 5 daqiqada majburan to'xtatiladi.
    task_soft_time_limit=240,
    task_time_limit=300,
    # OpenCV/PyMuPDF xotirani sekin qo'yib yuboradi — bola-jarayon vaqti-vaqti
    # bilan yangilanadi.
    worker_max_tasks_per_child=200,
)

# Vaqtinchalik fayllarni tozalash (weaknesses.md №30) — kuniga bir marta.
celery_app.conf.beat_schedule = {
    "cleanup-temp-files": {
        "task": "cleanup_temp_files",
        "schedule": 24 * 60 * 60.0,
    },
}


@worker_process_init.connect
def _reset_db_engine(**_kwargs) -> None:
    """
    Fork'dan keyin engine'ni tozalaydi.

    Ota-jarayon yaratgan psycopg2 soketlari bolalar orasida bo'linsa ulanish
    buziladi — har bola o'z pul'ini noldan yaratadi.
    """
    from app.worker.session import dispose_engine

    dispose_engine()

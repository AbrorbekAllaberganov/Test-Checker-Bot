import logging
import os
import queue
import sys
import threading
import time

# Loki navbati CHEGARALANGAN: ilgari `queue.Queue()` cheksiz edi va Loki
# yotganda har yozuv navbatda to'planib xotirani yeb borardi (weaknesses.md
# №31). To'lganda yangi yozuvlar tashlab yuboriladi — log yo'qolishi
# jarayonning o'limidan afzal.
LOKI_QUEUE_MAX = 2000
# Bir so'rovda yuboriladigan yozuvlar soni.
LOKI_BATCH_MAX = 50
# Navbat to'lgani haqida qancha vaqtda bir marta ogohlantirish (sekund).
LOKI_WARN_INTERVAL = 60.0
# Xatolikdan keyin kutish: eksponensial 1 → 30 s.
LOKI_BACKOFF_MIN = 1.0
LOKI_BACKOFF_MAX = 30.0


class LokiHandler(logging.Handler):
    """Grafana Loki log handler sending logs in a background thread."""

    def __init__(self, url: str, service_name: str) -> None:
        super().__init__()
        self.url = url
        self.service_name = service_name
        self.queue: queue.Queue[tuple[str, str, str]] = queue.Queue(
            maxsize=LOKI_QUEUE_MAX
        )
        self._dropped = 0
        self._last_warn = 0.0
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = self.format(record)
            try:
                self.queue.put_nowait((record.levelname, record.name, line))
            except queue.Full:
                self._note_drop()
        except Exception:
            pass

    def _note_drop(self) -> None:
        """Tashlangan yozuvlar haqida stderr'ga (Loki'ga emas!) xabar beradi."""
        self._dropped += 1
        now = time.monotonic()
        if now - self._last_warn >= LOKI_WARN_INTERVAL:
            self._last_warn = now
            print(
                f"[logging] Loki navbati to'lgan — {self._dropped} ta yozuv "
                "tashlab yuborildi",
                file=sys.stderr,
            )
            self._dropped = 0

    def _drain(self) -> list[tuple[str, str, str]]:
        """Navbatdan bir guruh yozuvni oladi (birinchisini bloklab kutadi)."""
        batch = [self.queue.get()]
        while len(batch) < LOKI_BATCH_MAX:
            try:
                batch.append(self.queue.get_nowait())
            except queue.Empty:
                break
        return batch

    def _worker(self) -> None:
        import json
        import urllib.request

        backoff = LOKI_BACKOFF_MIN

        while True:
            try:
                batch = self._drain()

                # Yozuvlar (level, logger) bo'yicha oqimlarga guruhlanadi —
                # Loki bitta so'rovda bir nechta stream qabul qiladi.
                streams: dict[tuple[str, str], list[list[str]]] = {}
                for level, name, line in batch:
                    ns = str(int(time.time() * 1e9))
                    streams.setdefault((level, name), []).append([ns, line])

                payload = {
                    "streams": [
                        {
                            "stream": {
                                "service": self.service_name,
                                "level": level,
                                "logger": name,
                            },
                            "values": values,
                        }
                        for (level, name), values in streams.items()
                    ]
                }
                req = urllib.request.Request(
                    self.url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=2.0) as f:
                    f.read()
                backoff = LOKI_BACKOFF_MIN
            except Exception:
                # Loki yotgan bo'lsa tobora uzoqroq kutamiz — har yozuv uchun
                # 3 soniya band bo'lib turmaymiz.
                time.sleep(backoff)
                backoff = min(backoff * 2, LOKI_BACKOFF_MAX)


def setup_logging(level: str = "INFO") -> None:
    """Standart logging formatini sozlash."""
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    root_logger = logging.getLogger()

    # Clean up existing handlers to avoid double logging
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)

    # Console Handler
    c_handler = logging.StreamHandler(sys.stdout)
    c_handler.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S"))
    root_logger.addHandler(c_handler)
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Loki Handler (agar URL berilgan bo'lsa)
    loki_url = os.getenv("LOKI_URL", "").strip()
    if loki_url:
        service_name = os.getenv("SERVICE_NAME", "omr-app").strip()
        l_handler = LokiHandler(loki_url, service_name)
        l_handler.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S"))
        root_logger.addHandler(l_handler)

    # Shovqinli loggerlarni tinchlashtirish
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("aiogram").setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

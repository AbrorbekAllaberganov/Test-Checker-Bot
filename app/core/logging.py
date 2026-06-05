import logging
import os
import queue
import sys
import threading


class LokiHandler(logging.Handler):
    """Grafana Loki log handler sending logs in a background thread."""
    def __init__(self, url: str, service_name: str) -> None:
        super().__init__()
        self.url = url
        self.service_name = service_name
        self.queue: queue.Queue[tuple[str, str, str]] = queue.Queue()
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = self.format(record)
            self.queue.put((record.levelname, record.name, line))
        except Exception:
            pass

    def _worker(self) -> None:
        import json
        import time
        import urllib.request

        while True:
            try:
                level, name, line = self.queue.get()
                ns = int(time.time() * 1e9)
                payload = {
                    "streams": [
                        {
                            "stream": {
                                "service": self.service_name,
                                "level": level,
                                "logger": name,
                            },
                            "values": [
                                [str(ns), line]
                            ]
                        }
                    ]
                }
                req = urllib.request.Request(
                    self.url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=2.0) as f:
                    f.read()
            except Exception:
                time.sleep(1.0)  # Loki down bo'lsa kutib turish


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

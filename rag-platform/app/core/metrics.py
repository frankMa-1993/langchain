from dataclasses import dataclass, field
from threading import Lock


@dataclass
class Metrics:
    lock: Lock = field(default_factory=Lock)
    http_requests: int = 0
    http_errors: int = 0
    chat_streams: int = 0
    ingest_completed: int = 0


METRICS = Metrics()


def inc_http() -> None:
    with METRICS.lock:
        METRICS.http_requests += 1


def inc_error() -> None:
    with METRICS.lock:
        METRICS.http_errors += 1


def inc_stream() -> None:
    with METRICS.lock:
        METRICS.chat_streams += 1


def inc_ingest_completed() -> None:
    with METRICS.lock:
        METRICS.ingest_completed += 1


def snapshot() -> dict:
    with METRICS.lock:
        return {
            "http_requests": METRICS.http_requests,
            "http_errors": METRICS.http_errors,
            "chat_streams": METRICS.chat_streams,
            "ingest_completed": METRICS.ingest_completed,
        }

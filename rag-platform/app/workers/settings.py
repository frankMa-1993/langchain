from arq.connections import RedisSettings

from app.config import get_settings
from app.workers.ingest import process_document


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    functions = [process_document]

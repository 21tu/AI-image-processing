from celery import Celery
from visionguard.core.config import get_settings
from visionguard.core.logging import setup_logging

settings = get_settings()
setup_logging(settings.log_level)
app = Celery("visionguard", broker=settings.redis_url)
app.conf.update(
    task_acks_late=True,
    task_default_queue="inference",
    worker_hijack_root_logger=False,
)


@app.task(name="visionguard.ping")
def ping() -> str:
    return "pong"

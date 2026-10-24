import json
import logging
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
        }
        if hasattr(record, "status_code"):
            payload["status_code"] = record.status_code
        for field in ("asset_id", "sha256", "size_bytes", "mime"):
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        return json.dumps(payload)


def setup_logging(level: str) -> None:
    root = logging.getLogger()
    root.setLevel(level)
    # Preserve caller-owned handlers (including pytest's capture handler).
    if not any(getattr(h, "visionguard_handler", False) for h in root.handlers):
        handler = logging.StreamHandler()
        handler.visionguard_handler = True
        handler.setFormatter(JsonFormatter())
        root.addHandler(handler)

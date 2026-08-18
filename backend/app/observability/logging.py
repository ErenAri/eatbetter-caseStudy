import json
import logging
from typing import Any


logger = logging.getLogger("eatbetter")


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def log_event(event: str, **fields: Any) -> None:
    safe = {key: value for key, value in fields.items() if value is not None}
    logger.info(json.dumps({"event": event, **safe}, default=str, separators=(",", ":")))

import logging
import sys
from datetime import datetime
from pathlib import Path


def setup_logger(output_folder: str | Path, run_started_at: datetime | None = None) -> logging.Logger:
    output_folder = Path(output_folder)
    logs_dir = output_folder / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    timestamp = run_started_at if run_started_at is not None else datetime.now()
    filename = timestamp.strftime("pipeline-%Y-%m-%d-%H%M-%S.log")
    log_path = logs_dir / filename

    logger = logging.getLogger("pipeline")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    return logger

import logging
import re
from datetime import datetime

from engine.logger import setup_logger


def test_creates_logs_dir_and_file(tmp_path):
    setup_logger(tmp_path)
    logs_dir = tmp_path / "logs"
    assert logs_dir.is_dir()
    log_files = list(logs_dir.glob("*.log"))
    assert len(log_files) == 1


def test_filename_matches_pattern(tmp_path):
    setup_logger(tmp_path)
    logs_dir = tmp_path / "logs"
    log_file = next(logs_dir.glob("*.log"))
    assert re.fullmatch(r"pipeline-\d{4}-\d{2}-\d{2}-\d{4}-\d{2}\.log", log_file.name)


def test_second_call_replaces_handlers(tmp_path):
    folder_a = tmp_path / "a"
    folder_b = tmp_path / "b"
    setup_logger(folder_a)
    logger = setup_logger(folder_b)
    assert len(logger.handlers) == 2


def test_second_call_writes_to_new_file(tmp_path):
    folder_a = tmp_path / "a"
    folder_b = tmp_path / "b"
    setup_logger(folder_a)
    setup_logger(folder_b)
    assert len(list((folder_a / "logs").glob("*.log"))) == 1
    assert len(list((folder_b / "logs").glob("*.log"))) == 1


def test_exception_traceback_preserved_in_file(tmp_path):
    logger = setup_logger(tmp_path)
    try:
        raise ValueError("something went wrong")
    except ValueError:
        logger.exception("caught an error")

    for handler in logger.handlers:
        handler.flush()

    log_file = next((tmp_path / "logs").glob("*.log"))
    content = log_file.read_text(encoding="utf-8")
    assert "Traceback" in content
    assert "ValueError" in content
    assert "something went wrong" in content


def test_uses_run_started_at_for_filename(tmp_path):
    fixed_time = datetime(2025, 3, 7, 9, 5, 42)
    setup_logger(tmp_path, run_started_at=fixed_time)
    log_file = next((tmp_path / "logs").glob("*.log"))
    assert log_file.name == "pipeline-2025-03-07-0905-42.log"

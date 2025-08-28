import json
from pathlib import Path

from pytest import CaptureFixture

from faster.core.logger import get_logger, setup_logger


def test_logger_json_file_output(tmp_path: Path) -> None:
    log_file = tmp_path / "test.log"
    setup_logger(log_format="json", log_file=str(log_file))
    logger = get_logger(__name__)

    msg = "This is a test message"
    logger.info(msg, extra_param="extra_value")

    with open(log_file) as f:
        log_content = f.readline()
        log_data = json.loads(log_content)
        assert log_data["event"] == msg
        assert log_data["extra_param"] == "extra_value"
        assert log_data["level"] == "info"


def test_logger_console_file_output(tmp_path: Path) -> None:
    log_file = tmp_path / "test.log"
    setup_logger(log_format="console", log_file=str(log_file))
    logger = get_logger(__name__)

    msg = "This is a plain text message"
    logger.warning(msg, data="some_data")

    with open(log_file) as f:
        log_content = f.readline()
        assert msg in log_content
        assert "[warning ]" in log_content
        assert "'data': 'some_data'" in log_content  # check for extra params
        # Check no color codes
        assert "e[33m" not in log_content


def test_console_output_is_always_plain_text(capsys: CaptureFixture[str], tmp_path: Path) -> None:
    log_file = tmp_path / "test.log"
    # Setup with json format for file
    setup_logger(log_format="json", log_file=str(log_file))
    logger = get_logger(__name__)

    msg = "Console test"
    logger.error(msg)

    captured = capsys.readouterr()
    # Check for colored output and no json
    assert "[31m" in captured.out  # red for error
    assert "[error   ]" in captured.out
    assert msg in captured.out

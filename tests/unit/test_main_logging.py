import logging
import re
import sys
from unittest.mock import patch

from src.main import _configure_mcp_logging


def test_runtime_log_format_includes_timestamp_source_and_traceback():
    with patch("src.main.logging.basicConfig") as configure:
        _configure_mcp_logging()
    options = configure.call_args.kwargs
    formatter = logging.Formatter(options["format"], datefmt=options["datefmt"])
    try:
        raise RuntimeError("test failure")
    except RuntimeError:
        record = logging.LogRecord(
            "pilot-test",
            logging.WARNING,
            "example.py",
            42,
            "Generation failed",
            (),
            sys.exc_info(),
        )
    output = formatter.format(record)
    assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{4}", output)
    assert "[WARNING] pilot-test (example.py:42): Generation failed" in output
    assert "Traceback (most recent call last)" in output
    assert "RuntimeError: test failure" in output
    assert "stream" not in options

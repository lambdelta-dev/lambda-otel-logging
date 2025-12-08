import logging
from unittest.mock import MagicMock, patch

import msgspec
import pytest
from botocore.exceptions import (
    DataNotFoundError,
)
from opentelemetry import trace
from pytest import CaptureFixture

from lambda_otel_logging.logging import OpenTelemetryLogFormatter, basic_config

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


def test_formatter_should_format_normal_log_records() -> None:
    formatter = OpenTelemetryLogFormatter()
    msg = formatter.format(
        logging.LogRecord(
            name="some_module",
            level=logging.INFO,
            pathname="/hello/world.py",
            lineno=80,
            msg="Testing message",
            args=(),
            exc_info=None,
            func="print_hello",
        )
    )
    decoded = msgspec.json.decode(msg)
    assert "Testing message" in decoded["body"]


def test_logging_happy(capsys: pytest.CaptureFixture[str]) -> None:
    logger = basic_config()

    logger.info("test message")
    logger.warning("test warning")
    logger.error("test error")
    try:
        raise ZeroDivisionError()
    except ZeroDivisionError:
        logger.exception("test exception")

    with tracer.start_as_current_span("parent", kind=trace.SpanKind.SERVER):
        logger.info("Parent span")
        with tracer.start_as_current_span("child"):
            logger.error("Child span")

    outerr = capsys.readouterr()
    captured = outerr.err + outerr.out
    assert "test message" in captured
    assert "test warning" in captured
    assert "test error" in captured
    assert "test exception" in captured
    assert "ZeroDivisionError" in captured


@patch("lambda_otel_logging.logging.json_encode")
def test_should_log_body_as_string(mock_encode: MagicMock) -> None:
    # Patch msgspec.json.encode to see if body is a string
    logger = basic_config()
    exp = DataNotFoundError(data_path="asdf")
    logger.info(exp)
    mock_encode.assert_called()

    # Get the first argument of the first call
    record_dict = mock_encode.call_args[0][0]
    assert isinstance(record_dict, dict)
    assert isinstance(record_dict["body"], str)


def test_should_log_object(capsys: CaptureFixture) -> None:
    # Patch msgspec.json.encode to see if body is a string
    logger = basic_config()
    exp = DataNotFoundError(data_path="asdf")
    logger.info(exp)
    captured = capsys.readouterr()
    assert (
        "Encoding objects of type DataNotFoundError is unsupported" not in captured.err
    )

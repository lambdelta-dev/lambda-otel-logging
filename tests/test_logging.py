import logging

import msgspec

from lambda_otel_logging.logging import basic_config, OpenTelemetryLogFormatter
from opentelemetry import trace

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


def test_formatter_should_format_normal_log_records():
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


def test_logging_happy(capsys) -> None:
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

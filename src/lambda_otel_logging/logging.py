import logging
from collections.abc import Sequence
from typing import Literal, TypeAlias

import msgspec
from opentelemetry.trace import SpanContext, get_current_span

logger = logging.getLogger(__name__)

LoggingLevel: TypeAlias = (
    Literal["CRITICAL"]
    | Literal["FATAL"]
    | Literal["ERROR"]
    | Literal["WARN"]
    | Literal["WARNING"]
    | Literal["INFO"]
    | Literal["DEBUG"]
    | Literal["NOTSET"]
)


def log_level_to_severity_number(level: int) -> int:
    """Convert a standard logging level to an OpenTelemetry severity number.

    Args:
        level (int): Standard logging level (e.g., logging.DEBUG, logging.INFO).

    Returns:
        int: Corresponding OpenTelemetry severity number.
    """
    # https://docs.python.org/3/library/logging.html#logging-levels
    # https://opentelemetry.io/docs/specs/otel/logs/data-model/#field-severitynumber
    if level >= logging.CRITICAL:
        return 24  # FATAL
    elif level >= logging.ERROR:
        return 16  # ERROR
    elif level >= logging.WARNING:
        return 12  # WARN
    elif level >= logging.INFO:
        return 9  # INFO
    elif level >= logging.DEBUG:
        return 5  # DEBUG
    else:
        return 1  # TRACE


class OpenTelemetryLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # https://opentelemetry.io/docs/specs/otel/logs/data-model/#log-and-event-record-definition
        otel_context = record.__dict__.pop("otel_context", {})
        body = record.msg % record.args if record.args else record.msg

        extra_attributes: dict[str, str] = record.__dict__.pop("otel_attributes", {})

        if record.exc_info:
            extra_attributes["exception.stacktrace"] = (
                logging.Formatter().formatException(record.exc_info)
            )
            extra_attributes["exception.message"] = str(record.exc_info[1])

        record_dict = {
            "body": body,
            "severityNumber": log_level_to_severity_number(record.levelno),
            "severityText": record.levelname.upper(),
            "timeUnixNano": int(record.created * 1_000_000_000),
            "spanId": format(otel_context.get("span_id", 0), "x"),
            "traceId": format(otel_context.get("trace_id", 0), "x"),
            "scope": {
                "name": record.name,
            },
            "attributes": {
                "code.file.path": record.pathname,
                "code.line.number": record.lineno,
                "code.function.name": record.funcName,
                **extra_attributes,
            },
        }
        return msgspec.json.encode(record_dict).decode("utf-8")


def log_record_factory(
    name,  # noqa: ANN001
    level,  # noqa: ANN001
    fn,  # noqa: ANN001
    lno,  # noqa: ANN001
    msg,  # noqa: ANN001
    args,  # noqa: ANN001
    exc_info,  # noqa: ANN001
    func=None,  # noqa: ANN001
    sinfo=None,  # noqa: ANN001
    **kwargs,  # noqa: ANN003
) -> logging.LogRecord:
    """Copy context we want to keep to the log record"""
    record = logging.LogRecord(
        name, level, fn, lno, msg, args, exc_info, func, sinfo, **kwargs
    )

    # Override extra in kwargs
    current_span = get_current_span()
    if current_span and current_span.get_span_context():
        ctx: SpanContext = current_span.get_span_context()

        record.__dict__["otel_context"] = {
            "trace_id": ctx.trace_id,
            "span_id": ctx.span_id,
        }

    if hasattr(current_span, "attributes"):
        record.__dict__["otel_attributes"] = {
            k: str(v) for k, v in current_span.attributes.items()
        }

    return record


def basic_config(
    level: LoggingLevel = "INFO",
    formatter: logging.Formatter | None = None,
    set_level_on: dict[LoggingLevel, Sequence[str]] | None = None,
) -> logging.Logger:
    """Basic configuration of the logger

    Will remove all other handlers from the root logger and install
    the log_record_factory and OpenTelemetryLogFormatter.

    A single new StreamHandler is added.

    Args:
        level (str, optional): Level to set on the root logger. Defaults to "INFO".
        formatter (logging.Formatter | None, optional): Optional other log formatter to use instead. Defaults to None.
        set_level_on (dict[str, Sequence[str]] | None, optional): Dictionary with logger you want to configure the log level on. Defaults to None.

    Returns:
        logging.Logger: The updated root logger
    """
    logging.setLogRecordFactory(log_record_factory)

    root = logging.getLogger()
    root.setLevel(level)

    # Remove other handlers
    for h in root.handlers[:]:
        root.removeHandler(h)

    handler = logging.StreamHandler()
    handler.setFormatter(formatter or OpenTelemetryLogFormatter())
    root.addHandler(handler)

    if set_level_on:
        for lvl, loggers in set_level_on.items():
            for log_name in loggers:
                logging.getLogger(log_name).setLevel(lvl)
    return root

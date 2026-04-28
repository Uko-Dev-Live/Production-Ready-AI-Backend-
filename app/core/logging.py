"""
app/core/logging.py
────────────────────
Structured JSON logging using structlog.

Why structured logging?
  • Every log line is valid JSON — easy to ingest into Grafana / ELK.
  • Fields like request_id, user_id, task_id can be attached to any log.
  • Much easier to search and filter than plain text logs.
"""

import logging
import structlog


def setup_logging(debug: bool = False) -> None:
    """Configure structlog for the entire application."""

    log_level = logging.DEBUG if debug else logging.INFO

    # Configure the standard library logger (used by uvicorn, SQLAlchemy, etc.)
    logging.basicConfig(
        format="%(message)s",
        level=log_level,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,          # thread-local context
            structlog.processors.add_log_level,               # add "level" field
            structlog.processors.StackInfoRenderer(),          # render stack info
            structlog.dev.set_exc_info,                       # attach exception info
            structlog.processors.TimeStamper(fmt="iso"),      # ISO 8601 timestamp
            structlog.dev.ConsoleRenderer() if debug          # pretty in dev
            else structlog.processors.JSONRenderer(),          # JSON in prod
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


# Module-level logger — import this in other modules
logger = structlog.get_logger(__name__)

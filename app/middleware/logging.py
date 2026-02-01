"""
Request logging middleware
Logs API request details (headers and timing only - body logging removed to avoid ASGI conflicts)
"""
import logging
import time
import json
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from config.settings import get_settings

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware:
    """
    Middleware to log API requests

    Note: Body logging is intentionally disabled to avoid ASGI receive() conflicts.
    Use endpoint-level logging if you need to log request bodies.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        settings = get_settings()
        start_time = time.time()

        # Extract request info from scope
        method = scope["method"]
        path = scope["path"]

        # Wrap send to capture response status
        status_code = None

        async def send_with_logging(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        # Log request in DEBUG mode (headers only)
        if settings.DEBUG or settings.LOG_LEVEL == "DEBUG":
            headers = {k.decode(): v.decode() for k, v in scope.get("headers", [])}
            logger.debug(f"Request: {method} {path}")
            logger.debug(f"Headers: {json.dumps(headers, ensure_ascii=False, indent=2)}")

        # Process request
        await self.app(scope, receive, send_with_logging)

        # Log response
        process_time = time.time() - start_time
        logger.info(
            f"{method} {path} - "
            f"Status: {status_code or 'unknown'} - "
            f"Time: {process_time:.3f}s"
        )

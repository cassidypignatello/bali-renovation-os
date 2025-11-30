"""
Request timeout middleware for FastAPI.

Prevents requests from hanging indefinitely by enforcing
configurable timeouts for different endpoint patterns.
"""

import asyncio
import time
from typing import Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class TimeoutMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce request timeouts.

    Different timeout limits for different endpoints:
    - Health/readiness: 5s (fast checks)
    - Standard endpoints: 30s (normal operations)
    - Heavy endpoints (estimates, scraping): 180s (3 minutes)

    Returns 504 Gateway Timeout if request exceeds limit.
    """

    def __init__(self, app, default_timeout: int = 30):
        """
        Initialize timeout middleware.

        Args:
            app: FastAPI application
            default_timeout: Default timeout in seconds
        """
        super().__init__(app)
        self.default_timeout = default_timeout

        # Endpoint-specific timeouts (in seconds)
        self.timeout_config = {
            "/health": 5,
            "/readiness": 5,
            "/metrics": 5,
            "/estimates/": 180,  # BOM generation + price enrichment
            "/workers/search": 60,  # OLX/Google Maps scraping
            "/materials/": 10,  # Database queries
            "/payments/": 10,  # Midtrans API calls
        }

    def get_timeout_for_path(self, path: str) -> int:
        """
        Get timeout limit for request path.

        Args:
            path: Request path

        Returns:
            int: Timeout in seconds
        """
        # Check for exact matches or prefix matches
        for pattern, timeout in self.timeout_config.items():
            if path.startswith(pattern):
                return timeout

        return self.default_timeout

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request with timeout enforcement.

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response: Either normal response or timeout error
        """
        start_time = time.time()
        timeout = self.get_timeout_for_path(request.url.path)

        try:
            # Execute request with timeout
            response = await asyncio.wait_for(call_next(request), timeout=timeout)

            # Add processing time header
            processing_time = time.time() - start_time
            response.headers["X-Processing-Time"] = f"{processing_time:.3f}s"

            return response

        except asyncio.TimeoutError:
            # Request exceeded timeout limit
            processing_time = time.time() - start_time
            return JSONResponse(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                content={
                    "error": "request_timeout",
                    "message": f"Request exceeded {timeout}s timeout limit",
                    "processing_time": f"{processing_time:.3f}s",
                    "timeout_limit": f"{timeout}s",
                    "ok": False,
                },
                headers={"X-Processing-Time": f"{processing_time:.3f}s"},
            )

        except Exception as e:
            # Other errors pass through to error handler
            raise e

"""Dependency-free HTTP helper (stdlib only - keeps the serverless bundle small)."""

from __future__ import annotations

import json
import logging
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings

from eld.exceptions import UpstreamServiceError

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = (0.4, 1.0)


def _config() -> dict:
    return settings.SPOTTER


def get_json(
    url: str,
    params: dict[str, Any] | None = None,
    *,
    timeout: float | None = None,
    accept: str = "application/json",
) -> Any:
    """GET ``url`` and decode the JSON body, retrying transient failures.

    Raises :class:`UpstreamServiceError` when every attempt fails.
    """
    config = _config()
    effective_timeout = timeout or float(config.get("HTTP_TIMEOUT_SECONDS", 25.0))
    query = f"?{urlencode(params, doseq=True)}" if params else ""
    full_url = f"{url}{query}"
    headers = {
        "User-Agent": config.get("USER_AGENT", "spotter-eld/1.0"),
        "Accept": accept,
        "Accept-Language": "en-US,en;q=0.9",
    }

    last_error: Exception | None = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            request = Request(full_url, headers=headers, method="GET")
            with urlopen(request, timeout=effective_timeout) as response:
                body = response.read().decode("utf-8", errors="replace")
            return json.loads(body)
        except HTTPError as exc:
            last_error = exc
            # 4xx other than 429 is a permanent client error - do not retry.
            if exc.code < 500 and exc.code != 429:
                logger.warning("Upstream %s returned HTTP %s", url, exc.code)
                raise UpstreamServiceError(
                    f"Upstream provider rejected the request (HTTP {exc.code}).",
                    details={"url": url},
                ) from exc
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            last_error = exc

        if attempt < _MAX_ATTEMPTS - 1:
            time.sleep(_BACKOFF_SECONDS[min(attempt, len(_BACKOFF_SECONDS) - 1)])

    logger.error("Upstream %s failed after %s attempts: %s", url, _MAX_ATTEMPTS, last_error)
    raise UpstreamServiceError(
        "Could not reach the routing/geocoding provider. Please try again.",
        details={"url": url},
    )

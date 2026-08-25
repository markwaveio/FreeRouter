from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from contextlib import closing
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Final, cast

from pydantic import JsonValue, TypeAdapter, ValidationError

from freerouter.errors import UnsupportedUrlError

if TYPE_CHECKING:
    from collections.abc import Mapping
    from http.client import HTTPResponse

JSON_ADAPTER: Final = TypeAdapter[JsonValue](JsonValue)

__all__ = [
    "JsonValue",
    "Response",
    "as_items",
    "as_price",
    "as_strings",
    "as_text",
    "dig",
    "request",
]

HTTP_OK: Final = 200
HTTP_REDIRECT: Final = 300
HTTP_UNAUTHORIZED: Final = 401
HTTP_PAYMENT_REQUIRED: Final = 402
HTTP_FORBIDDEN: Final = 403
HTTP_NOT_FOUND: Final = 404
HTTP_TOO_MANY_REQUESTS: Final = 429
HTTP_SERVER_ERROR: Final = 500

DEFAULT_TIMEOUT: Final = 30.0
ALLOWED_SCHEMES: Final = frozenset({"http", "https"})
USER_AGENT: Final = "FreeRouter/0.2 (+https://github.com/markwaveio/FreeRouter)"


@dataclass(frozen=True, slots=True)
class Response:
    status: int
    body: bytes

    @property
    def ok(self) -> bool:
        """Report whether the status code is a 2xx success."""
        return HTTP_OK <= self.status < HTTP_REDIRECT

    @property
    def text(self) -> str:
        """Decode the body, replacing undecodable bytes."""
        return self.body.decode(errors="replace")

    def json(self) -> JsonValue:
        """Parse the body as JSON, returning None when it is not valid JSON."""
        try:
            return JSON_ADAPTER.validate_json(self.body)
        except ValidationError:
            return None


def request(
    url: str,
    *,
    method: str = "GET",
    headers: Mapping[str, str] | None = None,
    payload: JsonValue = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Response:
    """Perform one HTTP request and return the status and raw body.

    Network and protocol failures are folded into a synthetic ``Response`` so that
    every caller can branch on a status code instead of catching exceptions.
    """
    if urllib.parse.urlsplit(url).scheme not in ALLOWED_SCHEMES:
        raise UnsupportedUrlError(url=url)

    body = None if payload is None else json.dumps(payload).encode()
    merged = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if body is not None:
        merged["Content-Type"] = "application/json"
    merged.update(headers or {})

    http_request = urllib.request.Request(url, data=body, headers=merged, method=method)  # noqa: S310 - scheme checked above
    try:
        opened = cast(
            "HTTPResponse",
            urllib.request.urlopen(http_request, timeout=timeout),  # noqa: S310 - scheme checked above
        )
        with closing(opened) as response:
            return Response(status=response.status, body=response.read())
    except urllib.error.HTTPError as error:
        return Response(status=error.code, body=error.read())
    except (OSError, urllib.error.URLError) as error:
        return Response(status=0, body=str(error).encode())


def dig(value: JsonValue, path: str) -> JsonValue:
    """Walk a dotted path through nested JSON objects, returning None when absent."""
    current = value
    for key in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def as_items(value: JsonValue) -> tuple[JsonValue, ...]:
    """Return a JSON array as a tuple, or an empty tuple for any other shape."""
    return tuple(value) if isinstance(value, list) else ()


def as_text(value: JsonValue) -> str | None:
    """Return a JSON string, or None for any other shape."""
    return value if isinstance(value, str) else None


def as_strings(value: JsonValue) -> tuple[str, ...]:
    """Return the string members of a JSON array, ignoring other members."""
    return tuple(item for item in as_items(value) if isinstance(item, str))


def as_price(value: JsonValue) -> Decimal | None:
    """Coerce a JSON price (string or number) to Decimal, or None when unusable."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        try:
            return Decimal(value)
        except InvalidOperation:
            return None
    return None

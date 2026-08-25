from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from freerouter.errors import GatewayError
from freerouter.transport import as_items, as_text, dig, request

if TYPE_CHECKING:
    from datetime import datetime

    from freerouter.planning import Deployment
    from freerouter.transport import JsonValue, Response

READY_POLL_SECONDS: Final = 3.0
CHAT_TIMEOUT: Final = 90.0
ADMIN_TIMEOUT: Final = 30.0
PROBE_TAG: Final = "freerouter-probe"


@dataclass(frozen=True, slots=True)
class Gateway:
    base_url: str
    master_key: str

    @property
    def headers(self) -> dict[str, str]:
        """Return the admin authorization headers."""
        return {"Authorization": f"Bearer {self.master_key}"}

    def wait_ready(self, timeout: float) -> bool:
        """Poll the liveliness endpoint until the proxy answers or the timeout elapses."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if request(f"{self.base_url}/health/liveliness", timeout=READY_POLL_SECONDS).ok:
                return True
            time.sleep(READY_POLL_SECONDS)
        return False

    def managed_ids(self) -> tuple[str, ...]:
        """List every deployment id the proxy currently serves."""
        response = request(
            f"{self.base_url}/model/info", headers=self.headers, timeout=ADMIN_TIMEOUT
        )
        if not response.ok:
            raise GatewayError(action="GET /model/info", status=response.status, body=response.text)
        return tuple(
            identifier
            for item in as_items(dig(response.json(), "data"))
            if (identifier := as_text(dig(item, "model_info.id"))) is not None
        )

    def add(self, deployment: Deployment) -> None:
        """Register one deployment without restarting the proxy."""
        response = request(
            f"{self.base_url}/model/new",
            method="POST",
            headers=self.headers,
            payload=deployment.payload(),
            timeout=ADMIN_TIMEOUT,
        )
        if not response.ok:
            raise GatewayError(
                action=f"POST /model/new {deployment.alias}",
                status=response.status,
                body=response.text,
            )

    def delete(self, identifier: str) -> None:
        """Remove one deployment without restarting the proxy."""
        response = request(
            f"{self.base_url}/model/delete",
            method="POST",
            headers=self.headers,
            payload={"id": identifier},
            timeout=ADMIN_TIMEOUT,
        )
        if not response.ok:
            raise GatewayError(
                action=f"POST /model/delete {identifier}",
                status=response.status,
                body=response.text,
            )

    def spend_logs(self, since: datetime | None = None) -> tuple[JsonValue, ...]:
        """Fetch LiteLLM's per-request log, bounded by date so it stays cheap to read."""
        query = f"?start_date={since.date().isoformat()}" if since else ""
        response = request(
            f"{self.base_url}/spend/logs{query}", headers=self.headers, timeout=ADMIN_TIMEOUT
        )
        if not response.ok:
            raise GatewayError(
                action="GET /spend/logs", status=response.status, body=response.text
            )
        payload = response.json()
        return as_items(payload) or as_items(dig(payload, "data"))

    def chat(self, alias: str, prompt: str, max_tokens: int) -> Response:
        """Send one minimal completion through the proxy, exactly as real traffic would.

        The request carries the probe tag so operators reading the call log can tell
        FreeRouter's own health checks apart from their application's traffic.
        """
        return request(
            f"{self.base_url}/v1/chat/completions",
            method="POST",
            headers=self.headers,
            payload={
                "model": alias,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "stream": False,
                "metadata": {"tags": [PROBE_TAG]},
            },
            timeout=CHAT_TIMEOUT,
        )

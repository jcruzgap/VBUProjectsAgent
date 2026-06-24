"""WIQL query execution and ID pagination."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import httpx

from .errors import AdoWiqlError

logger = logging.getLogger(__name__)


def execute_wiql(
    session: "httpx.Client",
    base_url: str,
    ado_project: str,
    wiql: str,
    api_version: str,
) -> list[int]:
    """Execute a WIQL query and return list of work item IDs."""
    url = f"{base_url}/{ado_project}/_apis/wit/wiql?api-version={api_version}"
    payload = {"query": wiql}

    try:
        resp = session.post(url, json=payload)
    except Exception as exc:
        from .errors import AdoNetworkError
        raise AdoNetworkError(f"Network error during WIQL execution: {exc}") from exc

    if resp.status_code == 400:
        body = _safe_body(resp)
        raise AdoWiqlError(
            f"WIQL query rejected by ADO (400). Server message: {body}. "
            f"Offending query: {wiql[:200]}"
        )

    _check_auth(resp)
    resp.raise_for_status()

    data = resp.json()
    items = data.get("workItems", [])
    return [item["id"] for item in items if "id" in item]


def _check_auth(resp: "httpx.Response") -> None:
    from .errors import AdoAuthError, AdoPatExpired
    if resp.status_code == 401:
        # Try to detect expiry from body
        body = _safe_body(resp).lower()
        if "expired" in body or "token lifetime" in body:
            raise AdoPatExpired("ADO PAT appears to have expired (HTTP 401).")
        raise AdoAuthError("ADO authentication failed (HTTP 401). Check PAT scopes.")
    if resp.status_code == 403:
        raise AdoAuthError("ADO authorization denied (HTTP 403). Check PAT permissions.")


def _safe_body(resp: "httpx.Response") -> str:
    try:
        return str(resp.json())
    except Exception:
        return resp.text[:500]

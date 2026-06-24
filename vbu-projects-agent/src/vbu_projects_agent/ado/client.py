"""Azure DevOps HTTP client — PAT auth, retries, batching."""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import time
from typing import Optional

import httpx

from ..config.models import AzureDevOpsConfig, FieldMappings, AdoGlobalConfig
from ..security.redaction import register_secret, redact
from .cache import AdoCache, get_cache
from .errors import AdoPatMissing, AdoNetworkError, AdoAuthError
from .wiql import execute_wiql, _check_auth
from .work_items import WorkItem, map_work_item

logger = logging.getLogger(__name__)


class AdoClient:
    """Authenticated Azure DevOps client with WIQL + batch fetch + caching."""

    def __init__(
        self,
        ado_config: AzureDevOpsConfig,
        field_mappings: FieldMappings,
        global_ado: AdoGlobalConfig,
        cache: Optional[AdoCache] = None,
    ) -> None:
        self.cfg = ado_config
        self.mappings = field_mappings
        self.global_ado = global_ado
        self.cache = cache or get_cache(global_ado.cache_ttl_seconds)
        self._session: Optional[httpx.Client] = None

    def _resolve_pat(self) -> str:
        pat = os.environ.get(self.cfg.pat_env_var, "").strip()
        if not pat:
            raise AdoPatMissing(
                f"ADO PAT not found in environment variable '{self.cfg.pat_env_var}'.",
                remediation=AdoPatMissing.remediation,
            )
        register_secret(pat)  # ensure it's always redacted
        return pat

    def _build_session(self, pat: str) -> httpx.Client:
        token = base64.b64encode(f":{pat}".encode()).decode()
        return httpx.Client(
            headers={
                "Authorization": f"Basic {token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    def _field_map_hash(self) -> str:
        raw = json.dumps(self.mappings.model_dump(), sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _retry(self, fn, *args, **kwargs):
        max_retries = self.global_ado.max_retries
        for attempt in range(max_retries + 1):
            try:
                return fn(*args, **kwargs)
            except AdoNetworkError:
                if attempt >= max_retries:
                    raise
                wait = 2 ** attempt
                logger.warning("ADO network error, retry %d/%d in %ds", attempt + 1, max_retries, wait)
                time.sleep(wait)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    retry_after = int(exc.response.headers.get("Retry-After", 5))
                    logger.warning("ADO rate limited, waiting %ds", retry_after)
                    time.sleep(retry_after)
                    if attempt >= max_retries:
                        raise AdoNetworkError("ADO rate limiting persists after retries.") from exc
                else:
                    raise

    def fetch_work_items(
        self,
        wiql: str,
        no_cache: bool = False,
    ) -> list[WorkItem]:
        """Full pipeline: WIQL → IDs → batch fetch → normalized WorkItems."""
        api_version = self.cfg.api_version or self.global_ado.default_api_version
        fmap_hash = self._field_map_hash()

        if not no_cache:
            cached = self.cache.get(
                self.cfg.project, wiql, fmap_hash, api_version
            )
            if cached is not None:
                logger.debug("ADO cache hit for project %s", self.cfg.project)
                return cached

        pat = self._resolve_pat()
        session = self._build_session(pat)

        try:
            ids = self._retry(
                execute_wiql,
                session,
                self.cfg.base_url,
                self.cfg.project,
                wiql,
                api_version,
            )
            logger.info("ADO WIQL returned %d work item IDs", len(ids))

            if not ids:
                return []

            items = self._fetch_batch(session, ids, api_version)
        finally:
            session.close()

        work_items = [map_work_item(raw, self.mappings) for raw in items]
        self.cache.set(self.cfg.project, wiql, fmap_hash, api_version, work_items)
        return work_items

    def _fetch_batch(
        self, session: httpx.Client, ids: list[int], api_version: str
    ) -> list[dict]:
        """Fetch work item details in batches of ≤ batch_size."""
        batch_size = self.global_ado.batch_size
        url = f"{self.cfg.base_url}/_apis/wit/workitemsbatch?api-version={api_version}"
        fields_to_request = list(self.mappings.model_dump().values())
        results: list[dict] = []

        for i in range(0, len(ids), batch_size):
            batch_ids = ids[i : i + batch_size]
            payload = {"ids": batch_ids, "fields": fields_to_request}
            try:
                resp = session.post(url, json=payload)
            except Exception as exc:
                raise AdoNetworkError(f"Network error during batch fetch: {exc}") from exc
            _check_auth(resp)
            resp.raise_for_status()
            batch_data = resp.json()
            results.extend(batch_data.get("value", []))

        return results

    def test_connectivity(self) -> bool:
        """Light probe to check ADO reachability and PAT validity."""
        try:
            pat = self._resolve_pat()
        except AdoPatMissing:
            return False
        session = self._build_session(pat)
        try:
            url = f"{self.cfg.base_url}/_apis/projects?api-version={self.cfg.api_version}&$top=1"
            resp = session.get(url)
            return resp.status_code in (200, 203)
        except Exception:
            return False
        finally:
            session.close()

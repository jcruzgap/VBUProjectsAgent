"""Risk Analysis skill — prose risk narrative from structured risk data."""
from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..claude.provider import ClaudeProvider

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are a delivery-status writing assistant for an executive audience. "
    "Reference ONLY the risks listed in the input. Do not invent risks or modify IDs."
)

_PROMPT = """\
[INPUT]
risks: {risks_json}
[TASK]
Summarize the risk posture in 2-4 sentences of prose: lead with the highest-severity/oldest
open risks, note aging (e.g., "open 17 days"), and mitigation status.
Reference only listed risks by their ID.
"""


def generate_risk_analysis(
    risks: list[dict],
    provider: Optional["ClaudeProvider"],
    model: Optional[str] = None,
) -> str:
    if not risks:
        return "No open risks at this time."
    if not provider:
        return _fallback_risk(risks)

    import json
    from datetime import date
    # Compute age for each risk
    enriched = []
    today = date.today()
    for r in risks:
        opened = r.get("opened_at", "")
        age_days = ""
        if opened:
            try:
                opened_d = date.fromisoformat(opened[:10])
                age_days = f"{(today - opened_d).days} days"
            except ValueError:
                pass
        enriched.append({**r, "age": age_days})

    prompt = _PROMPT.format(risks_json=json.dumps(enriched, default=str, indent=2))

    try:
        result = provider.complete(
            system=_SYSTEM,
            prompt=prompt,
            max_tokens=400,
            temperature=0.2,
            model=model,
        )
        return result.content.strip()
    except Exception as e:
        logger.warning("Risk analysis generation failed: %s", e)
        return _fallback_risk(risks)


def _fallback_risk(risks: list[dict]) -> str:
    open_risks = [r for r in risks if r.get("status") != "closed"]
    high = [r for r in open_risks if r.get("severity") in ("high", "critical")]
    lines = [f"Open risks: {len(open_risks)} total, {len(high)} high/critical."]
    for r in high[:3]:
        lines.append(f"- {r.get('id', '?')} ({r.get('severity', '?')}): {r.get('description', '')[:80]}")
    return " ".join(lines)

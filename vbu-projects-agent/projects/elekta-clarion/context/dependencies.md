---
content_sha256: d69093ba9d5f575cb181ae66452a0f977d78cea32af2567c849dc7bcbf11b72c
last_update_source: agent
last_updated: '2026-07-02T15:25:07.855697+00:00'
---
# Dependencies

| ID | Description | Prob | Impact | Owner | Notes |
|---|---|---|---|---|---|
| D1 | Elekta must run regression testing suite (600 Clarion TCs) to surface bugs before GAP can address them | H | H | Carla Frazior (Elekta) | Active blocker since Mar 23 |
| D2 | Code updates from Elekta (periodic) — each update triggers a rebase + stabilization cycle | M | H | Phillip Smith (Elekta) | Transferred from Josh Devine — confirm Phillip is the right owner for code updates |
| D3 | Exhibit N signature required to formally trigger M1 ($75K) payment — reviewer was out; back Jun 3 | M | H | Ron Langer / Carla Frazior (Elekta) | Joseph to follow up by Jun 5 if no confirmation |

## Notes
- Both E-e Clarion and Exhibit N milestones require TCs to pass **in Elekta's environment** — dependent on Carla running the regression suite (D1 / I2).
- C++ DLLs (Josh's items) not working in GAP environment block a subset of EF bugs and TCs — dependent on Carla's follow-up.

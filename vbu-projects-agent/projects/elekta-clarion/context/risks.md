---
content_sha256: eb72edad114ec9ed4f7b9159f26107a1e606f8a9646364cc3be46072af60e028
last_update_source: agent
last_updated: '2026-07-02T15:25:07.846384+00:00'
---
# Risks

## Active risks & issues (RAID summary)
| ID | Type | Description | Prob | Impact | Owner | Mitigation |
|---|---|---|---|---|---|---|
| I1 | Action | M1 delivered Jun 3 — confirm Exhibit N signature with Elekta to trigger $75K invoice | L | H | Joseph Cruz | Delivery done Jun 3; Exhibit N reviewer back Jun 3 — follow up by Jun 5 if no confirmation |
| I2 | Issue | Elekta has NOT run regression testing suite against 600 Clarion TCs — blocked since Mar 23 | H | H | Carla Frazior (Elekta) | Escalate — this blocks understanding of bug exposure before TC milestones |
| I3 | Issue | "Rules of Engagement" proposal with Elekta still not finalized — open since Mar 5 | M | M | Phillip Smith (Elekta) | Transferred from Josh Devine — re-introduce and confirm status with Phillip at first sync |
| R1 | Risk | Clarion TCs at 0/608 — E-e Clarion ($437,500) requires 8 TCs passing; TC execution started but no TCs yet on main branch | M | H | José Luis Pérez | TC-57 porting to main branch targeting Jun 9; 4 TCs in parallel — monitor weekly |
| R2 | Risk | 96 open EF bugs (53 GAP) — final IdeaBlade milestone payments require acceptable bug level | M | M | EF Alpha Team | Down from 101; C++ DLL-dependent bugs blocked on Carla response — monitor |
| R3 | Risk | Emulator VM performance (Hyper-V) — GAP PoC showed no improvement, research ongoing | M | M | Phillip Smith (Elekta) | Transferred from Josh Devine — confirm Phillip has context on this issue |
| R4 | Risk | Josh Devine's departure creates context gap — Rules of Engagement, emulator issue, Veracode scan, and relationship history all lived with him | H | H | Joseph Cruz | Establish relationship with Phillip Smith immediately; brief him on all open items at first sync |
| R5 | Risk | M2 (Window Handling, $100K) due Jun 30 — no progress mentioned in Jun 2 meeting; 26 days remaining | H | H | José Luis Pérez / Joseph Cruz | Immediate: confirm current M2 work status and whether Jun 30 is achievable |
| R6 | Risk | M5 acceptance requires 120 TCs passing **in Elekta's environment** — Carla's regression testing has been blocked since Mar 23 (I2). $350K at risk. | H | H | Carla Frazior (Elekta) | Escalate as revenue-critical — Aug 31 deadline requires Elekta to start running tests now |
| I4 | Issue | C++ DLLs (Josh's items) not working on GAP environment — blocking specific EF bugs and TCs. Carla tagged on Slack by Josh. | M | M | Carla Frazior (Elekta) | Carla confirmed follow-up in Jun 2 meeting — flag if no response by Jun 6 |

---
content_sha256: b5d8ddc02a5f49d0f745d93d5d51add7a5b07d4e3f922279048f1b731a4846ad
last_update_source: agent
last_updated: '2026-07-02T15:25:07.824299+00:00'
---
# Overview

## Snapshot
- **Client / Sponsor:** Elekta
- **Project:** MOSAIQ Modernization — Clarion component (Clarion → C#) + IdeaBlade/Entity Framework component
- **Delivery Manager:** Joseph Cruz (GAP, since Apr 2026, replacing William Méndez)
- **Current phase:** M1 (Integrated Build, zero Clarion DLL dependencies) delivered Jun 3 — 5 days late (due May 29). Exhibit N pending signature. M2 (Window Handling, $100K) due Jun 30 — next near-term milestone, no visible progress confirmed yet.
- **Current RAG:** 🟡 (M1 delivered Jun 3, 5 days late; Exhibit N not yet signed. M2 ($100K) due Jun 30 — no confirmed progress. 96 open EF bugs.)

## What MOSAIQ does
MOSAIQ is Elekta's radiation oncology treatment management system — used by hospitals and cancer centers worldwide to manage patient treatment plans, delivery of radiation therapy, clinical workflows, and oncology data. It is FDA-regulated (Class II medical device software), which makes SOUP compliance mandatory.

The modernization converts MOSAIQ from its legacy Clarion language + IdeaBlade ORM to C#/modern stack, enabling Elekta to maintain, extend, and support the product going forward.

## Scope & approach
- **Clarion → C#:** Automated migration of MOSAIQ's Clarion code using GAP's AI Migrator Tool (~1.8M lines of generated C# code). Manual resolution of compilation errors and integration work required post-automation.
- **IdeaBlade → Entity Framework:** Full replacement of IdeaBlade ORM with Entity Framework. 316 test cases.
- **SOUP (FDA compliance):** Upgrading/replacing all 3rd-party software dependencies (20+ libraries) to versions that meet FDA Class II medical device requirements. Phase 1 mostly done; Phase 2 in progress.
- **Test strategy:** 608 Clarion TCs + 316 EF TCs + future "Modern Architect" TCs. Gated milestone payments based on TC pass counts.
- Code updates received periodically from Elekta (last: Apr 8, 2026) require full rebase + stabilization cycle.

## North star
**600 Clarion TCs passing in Elekta's environment by Dec 31, 2026.** Hard deadline — cannot slip to 2027. Hitting it triggers Exhibit N M10 ($500K bonus) + all incremental original contract milestones (E-e Clarion $437,500 + E2-f2/f3/f4/f5/f6 $586,250 + E2-g5 through g11 $560,000). Plan V3 baseline had 600 TCs in Aug 2027 — this is an 8-month acceleration.

# Task: Second-brain recovery and resilience

Date: 2026-09-30
Role: Sigrun, acting as Cartographer, Architect, Forge Worker, Auditor and Scribe.

## Authorization and target

Volmarr requested discovery, restoration, robustness improvements and GitHub pushes for the installed second brain. This task records that authorized scope before implementation.

## Existing system

The knowledge store contains 1234 documents and 49003 embedded chunks. Bifrost, Skein, Skry and the private local ingest watcher share PostgreSQL and Ollama. Bifrost is running but binds only to the tailnet interface; a plain page visit requires a token and does not offer a login form. Skein has 8586 entities and 26339 relations. All existing tests pass.

## Owning domain and planned work

Eww: Preserve the installed GPU widget additions and publish them; make the collector recover from corrupt CPU cache and optional metrics failures; emit complete JSON defaults; use dynamically resolved install paths. Files: scripts/sysinfo.py, eww.yuck, eww.scss, tests/, README.md.

## Invariants

Preserve original corpus, user configuration and private files. Keep public response contracts and source ownership. Skry remains read-only. Skein owns only its derived tables. No secrets or corpus documents enter Git commits. No destructive schema changes or history rewrites. Keep failed inputs recoverable.

## Verification

Add regression tests for observed failure paths, run existing tests, validate service units, exercise live graph/search/Skry endpoints and inbox ingestion. Verify restart and outage recovery. Inspect staged diffs for accidental data/credentials before committing and pushing.

## Sequence

1. Preserve local sources, configs and database backup.
2. Commit and push this task document.
3. Implement the scoped fixes and regression tests.
4. Deploy locally and verify behavior.
5. Update architecture/interface/devlog documentation and push verified changes.

## Completed verification

2026-09-30: 2 tests pass for damaged CPU history and missing metrics. The live
collector emits valid complete JSON, including the RTX 2060 GPU metrics. Updated
configuration, collector and JSON defaults were installed; eww reload succeeds.
The NVIDIA driver repair and Ollama GPU inference were verified on the local host.
Install sysinfo.defaults.json alongside sysinfo.py as documented in README.md.

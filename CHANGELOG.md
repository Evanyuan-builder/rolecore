# CHANGELOG

## v0.1.1 — 2026-04-23

Technical-debt + ergonomics pass.

- `find --verdict {approved,needs_work,rejected}` — filter fusion search results by review verdict; complements `--status`
- Reviewer now mirrors `verdict + score + reviewed_at` into the registry entry's `meta.review` on attach, so verdict filtering works without rescanning YAMLs
- `registry resync` extended to pull review verdict from YAML back into the registry (for drift recovery)
- Internal: `build_parser` and `cmd_review_batch` split into small helpers — no CLI surface change
- Tests: 39 → 42

## v0.1.0 — 2026-04-23

Initial public showcase release.

- Core package: schema validation, 10-item official gate, five-level state machine (raw_imported → normalized → curated → official → archived)
- Three-axis fusion search (job × tech × specialty)
- LLM-assisted reviewer (5-dimension rubric, Anthropic + Ollama backends)
- 105 sample roles across 31 groups, all passing the reviewer gate
- Apache-2.0 licensed

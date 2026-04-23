# RoleCore

> YAML-based role asset management for LLM agents — content-addressed, gated, searchable.

Treat an "agent role" the way you'd treat a production asset: a version, a lifecycle, a signed checksum, a gate before it goes live.

- **105 sample roles** across 26 groups, shipped as a reference dataset
- **Five-level lifecycle**: `raw_imported → normalized → curated → official → archived` (forward-only state machine)
- **Two gates**: 10-item structural gate (`official`) + LLM 5-dimension review (`curated`)
- **Three-axis fusion search**: job × tech × specialty — ranked per-axis plus a triad pick
- **39 pytest, all green**

## Install

```bash
pip install rolecore
```

Requires Python 3.10+. Only runtime dependency is `PyYAML`. Optional: `anthropic` for live review.

## Quick tour

```bash
# Three-axis fusion search
rolecore find "python backend testing"

# Browse the bundled 105-role dataset
rolecore registry stats
rolecore role list --group engineering

# Assemble a role into a ready-to-use prompt
rolecore assemble --id engineering.backend_architect \
    --task "design an order service" --goal "support 10k QPS"

# Offline review (produces a prompt you paste into any LLM)
rolecore review prompt --id engineering.backend_architect

# Live review via Anthropic or local Ollama
ANTHROPIC_API_KEY=sk-... rolecore review run --id <role>
rolecore review run --id <role> --backend ollama --model qwen3:8b
```

Or use the Python API:

```python
from rolecore import create_default_engine, create_fusion_engine

rm, search, assembler = create_default_engine()
fusion = create_fusion_engine()

hits = fusion.find("backend python api", top_k_per_axis=3)
for axis in ("job", "tech", "specialty"):
    for hit in hits[axis]:
        print(axis, hit.entry.role_id, hit.score)
```

See `examples/load_and_find.py` and `examples/validate_yaml.py` for runnable walkthroughs.

## Core concepts

**Role YAML shape** — 9 required sections:

```
meta / identity / mission / boundaries / io / behavior / workflows / capabilities / evaluation
```

**The `official` gate (10 rules)** — structural checks before a role can be declared production-ready. The hardest one: `identity.name_cn` is a human-confirmation gate — the importer suggests, a human ratifies. Never auto-filled.

**The `curated` gate** — requires a review record with verdict `approved`. Reviews grade five dimensions: coherence, specificity, actionability, boundaries, evaluation. Scored 1–5, verdict ∈ {approved, needs_work, rejected}.

**State machine is forward-only.** A role at `official` can't move back to `curated` — the review still attaches (retroactive quality signal), but the status doesn't regress.

Read more in [docs/concepts.md](docs/concepts.md).

## Repository layout

```
rolecore-showcase/
├── rolecore/           core package (schema, gates, state machine, fusion search, reviewer)
├── roles/              105 reference roles (all passing both gates)
├── registry/           registry.json — the YAML registry index
├── schema/             role_schema.yaml
├── cli.py              CLI entry
├── tests/              39 pytest cases
├── docs/               concepts / architecture / cli / extending / reviewer
└── examples/           load_and_find.py · validate_yaml.py
```

## Docs

- [concepts.md](docs/concepts.md) — lifecycle, gates, governance invariants
- [architecture.md](docs/architecture.md) — module boundaries and data flow
- [cli.md](docs/cli.md) — command reference
- [extending.md](docs/extending.md) — writing your own role / new axis
- [reviewer.md](docs/reviewer.md) — LLM review workflow

## What's not in this repo

This is a showcase release. Upstream importers, the full 493-role dataset, operations tooling (drift monitor, batch reimporter), and the internal change log live in a separate private repository. If you're interested in the full system, reach out.

## Tests

```bash
pytest
```

39 passing. No network, no LLM; everything exercises schema, gate, state machine, search, and review-record plumbing against local fixtures.

## License

[Apache-2.0](LICENSE)

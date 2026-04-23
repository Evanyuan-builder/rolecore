from ..models.role import VALID_STATUSES, _LEGACY_STATUS_MAP

REQUIRED_TOP_KEYS = [
    "meta", "identity", "mission", "boundaries",
    "io", "behavior", "workflows", "capabilities", "evaluation",
]

_ALL_VALID_STATUSES = VALID_STATUSES | set(_LEGACY_STATUS_MAP.keys())

SECTION_RULES = {
    "meta": {
        "required": ["role_id", "version", "group", "tags", "status"],
        "list_fields": ["tags"],
    },
    "identity": {
        "required": ["name_cn", "name_en", "domain", "positioning"],
    },
    "mission": {
        "required": ["summary", "core_accountability"],
        "list_fields": ["core_accountability"],
    },
    "boundaries": {
        "required": ["can_do", "cannot_do", "escalate_when"],
        "list_fields": ["can_do", "cannot_do", "escalate_when"],
    },
    "io": {
        "required": ["inputs", "outputs"],
        "list_fields": ["inputs", "outputs"],
    },
    "behavior": {
        "required": ["communication_style", "risk_preference", "decision_approach", "collaboration_mode"],
    },
    "capabilities": {
        "required": ["tools", "knowledge", "context_requirements", "runtime_conditions"],
        "list_fields": ["tools", "knowledge", "context_requirements", "runtime_conditions"],
    },
    "evaluation": {
        "required": ["metrics", "success_criteria"],
        "list_fields": ["metrics", "success_criteria"],
    },
}


class SchemaValidationError(Exception):
    def __init__(self, errors: list):
        self.errors = errors
        super().__init__("Schema validation failed:\n" + "\n".join(f"  - {e}" for e in errors))


class SchemaValidator:
    def validate(self, data: dict) -> list:
        errors = []

        if not isinstance(data, dict):
            return ["Root document must be a mapping"]

        for key in REQUIRED_TOP_KEYS:
            if key not in data:
                errors.append(f"Missing top-level key: '{key}'")

        for section, rules in SECTION_RULES.items():
            section_data = data.get(section)
            if not isinstance(section_data, dict):
                if section != "workflows":
                    errors.append(f"'{section}' must be a mapping")
                continue

            for field in rules.get("required", []):
                if field not in section_data:
                    errors.append(f"'{section}.{field}' is required")
                elif section_data[field] is None:
                    errors.append(f"'{section}.{field}' must not be null")

            for field in rules.get("list_fields", []):
                if field in section_data and not isinstance(section_data[field], list):
                    errors.append(f"'{section}.{field}' must be a list")

        workflows = data.get("workflows")
        if workflows is not None:
            if not isinstance(workflows, list):
                errors.append("'workflows' must be a list")
            else:
                for i, w in enumerate(workflows):
                    if not isinstance(w, dict):
                        errors.append(f"'workflows[{i}]' must be a mapping")
                        continue
                    if "name" not in w:
                        errors.append(f"'workflows[{i}].name' is required")
                    if "steps" not in w:
                        errors.append(f"'workflows[{i}].steps' is required")
                    elif not isinstance(w["steps"], list):
                        errors.append(f"'workflows[{i}].steps' must be a list")

        meta = data.get("meta", {})
        if isinstance(meta, dict):
            status = meta.get("status", "")
            if status and status not in _ALL_VALID_STATUSES:
                errors.append(
                    f"'meta.status' is '{status}', must be one of: "
                    + ", ".join(sorted(_ALL_VALID_STATUSES))
                )

        return errors

    def validate_or_raise(self, data: dict) -> None:
        errors = self.validate(data)
        if errors:
            raise SchemaValidationError(errors)


# ─── Official gate ─────────────────────────────────────────────────────────────

# Placeholder strings inserted by the best-effort importer — considered empty.
# Rule: only patterns that are genuinely content-free or self-referential.
# Do NOT add boundary/scope statements here — a generic boundary is still a real constraint.
_PLACEHOLDER_PATTERNS = [
    "execute tasks within defined role scope",
    # "act outside defined role boundaries" — removed: generic but semantically real,
    # not a false placeholder. agency-agents upstream legitimately produces this.
    "task requirements exceed role capabilities",
    "task description and goal",
    "completed work product as specified",
    "standard tools for ",
    "domain expertise in ",
    "llm with role context loaded",
    "access to required tools",
    "task completion quality",
    "delivery accuracy",
    "deliverables meet specified quality",
    "task objectives are fully achieved",
    "output is actionable",
]


def _is_placeholder(text: str) -> bool:
    t = text.lower().strip()
    return any(t.startswith(p) for p in _PLACEHOLDER_PATTERNS)


def _real_items(lst: list, min_len: int = 10) -> list:
    """Filter out short strings and known importer placeholders."""
    return [x for x in lst if isinstance(x, str) and len(x) >= min_len and not _is_placeholder(x)]


class OfficialGateValidator:
    """
    Checks whether a role meets the minimum bar for 'official' status.
    Returns a list of gap descriptions (empty list = passes).

    Minimum requirements for official:
      - identity.name_cn  filled (non-empty)
      - identity.positioning  >= 60 chars
      - mission.summary  >= 80 chars
      - mission.core_accountability  >= 3 real items
      - boundaries.can_do  >= 3 real items
      - boundaries.cannot_do  >= 1 real item  (upstream format yields ~1; ≥2 was a rule mismatch)
      - behavior.communication_style  >= 30 chars and not a placeholder
      - workflows  >= 1 workflow with >= 3 real steps
      - evaluation.metrics  >= 2 real items
      - evaluation.success_criteria  >= 2 real items
    """

    def check(self, data: dict) -> list:
        gaps = []

        identity = data.get("identity", {})
        mission = data.get("mission", {})
        boundaries = data.get("boundaries", {})
        behavior = data.get("behavior", {})
        workflows = data.get("workflows", [])
        evaluation = data.get("evaluation", {})

        # identity
        if not identity.get("name_cn", "").strip():
            gaps.append("identity.name_cn is empty — fill in the Chinese name")
        pos = identity.get("positioning", "")
        if len(pos.strip()) < 60:
            gaps.append(f"identity.positioning too short ({len(pos.strip())} chars, need ≥60)")

        # mission
        summary = mission.get("summary", "")
        if len(summary.strip()) < 80:
            gaps.append(f"mission.summary too short ({len(summary.strip())} chars, need ≥80)")
        acct = _real_items(mission.get("core_accountability", []))
        if len(acct) < 3:
            gaps.append(f"mission.core_accountability has {len(acct)} real item(s), need ≥3")

        # boundaries
        can = _real_items(boundaries.get("can_do", []))
        if len(can) < 3:
            gaps.append(f"boundaries.can_do has {len(can)} real item(s), need ≥3")
        # cannot_do threshold is ≥1, not ≥2.
        # agency-agents upstream typically yields only one boundary statement; that is
        # a source-format characteristic, not a quality defect. Requiring ≥2 was a
        # rule mismatch (误伤) — ≥1 is the true governance floor.
        cannot = _real_items(boundaries.get("cannot_do", []))
        if len(cannot) < 1:
            gaps.append(f"boundaries.cannot_do is empty — at least one constraint required")

        # behavior
        comm = behavior.get("communication_style", "")
        if len(comm.strip()) < 30 or _is_placeholder(comm):
            gaps.append(f"behavior.communication_style too generic or short ('{comm[:60]}')")

        # workflows
        good_wf = [
            w for w in (workflows or [])
            if isinstance(w, dict) and len(_real_items(w.get("steps", []), min_len=8)) >= 3
        ]
        if not good_wf:
            gaps.append("no workflow with ≥3 meaningful steps found")

        # evaluation
        metrics = _real_items(evaluation.get("metrics", []))
        if len(metrics) < 2:
            gaps.append(f"evaluation.metrics has {len(metrics)} real item(s), need ≥2")
        criteria = _real_items(evaluation.get("success_criteria", []))
        if len(criteria) < 2:
            gaps.append(f"evaluation.success_criteria has {len(criteria)} real item(s), need ≥2")

        return gaps

"""LLM-assisted role quality reviewer.

The reviewer produces (or consumes) a structured review record stored under
`meta.review` in the role YAML. The review is separate from `meta.status` —
it acts as a gate on `raw_imported/normalized → curated` transitions but does
NOT retroactively demote roles already at `official`.

Verdicts:
  approved     — content is coherent, useful, and production-ready
  needs_work   — salvageable but has concrete gaps that the author must fix
  rejected     — content is generic, contradictory, or low-signal; discard

Score: integer 1-5 (5 = excellent, 1 = unusable).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


VALID_VERDICTS = ("approved", "needs_work", "rejected")

REVIEW_SYSTEM_PROMPT = (
    "You are a senior technical reviewer evaluating role-definition YAML "
    "assets for a role asset management system (RoleCore). Roles are used as "
    "executable prompts for LLM agents performing a defined job. Your task is "
    "to produce a terse structured review of one role.\n\n"
    "Evaluate along these dimensions:\n"
    "  1. Coherence — do identity, mission, boundaries, and workflows tell a "
    "consistent story about one role (not a generic template)?\n"
    "  2. Specificity — is the content actually tailored to this role, or is "
    "it boilerplate that could apply to anything?\n"
    "  3. Actionability — are workflow steps concrete enough for an LLM agent "
    "to follow without guessing?\n"
    "  4. Boundaries — are can_do / cannot_do constraints realistic and not "
    "contradictory with the positioning?\n"
    "  5. Evaluation — do metrics and success_criteria reflect what this role "
    "actually owns?\n\n"
    "Output STRICT JSON with this shape and no extra commentary:\n"
    "{\n"
    '  "verdict": "approved" | "needs_work" | "rejected",\n'
    '  "score": <1..5 integer>,\n'
    '  "strengths": ["<one line>", ...],   // 1-3 items\n'
    '  "issues":    ["<one line>", ...],   // 0-5 items, required if verdict != approved\n'
    '  "fix_hints": ["<actionable fix>", ...]   // 0-5 items, required if verdict = needs_work\n'
    "}\n"
    "Be stingy with 'approved' — reserve it for genuinely production-ready "
    "content. Default to 'needs_work' whenever you see generic placeholder "
    "text, a workflow that could apply to any role, or an evaluation metric "
    "that is too vague to measure."
)


@dataclass
class ReviewRecord:
    verdict: str
    score: int
    strengths: list
    issues: list
    fix_hints: list
    reviewer_model: str = ""
    reviewed_at: str = ""
    prompt_version: str = "v1"

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "score": self.score,
            "strengths": list(self.strengths),
            "issues": list(self.issues),
            "fix_hints": list(self.fix_hints),
            "reviewer_model": self.reviewer_model,
            "reviewed_at": self.reviewed_at,
            "prompt_version": self.prompt_version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ReviewRecord":
        return cls(
            verdict=d.get("verdict", ""),
            score=int(d.get("score", 0)),
            strengths=list(d.get("strengths", [])),
            issues=list(d.get("issues", [])),
            fix_hints=list(d.get("fix_hints", [])),
            reviewer_model=d.get("reviewer_model", ""),
            reviewed_at=d.get("reviewed_at", ""),
            prompt_version=d.get("prompt_version", "v1"),
        )


class ReviewParseError(ValueError):
    pass


def build_user_prompt(role_data: dict) -> str:
    """Render a compact text view of the role for the reviewer prompt."""
    import yaml

    # We pass the full YAML — it's the source of truth, and LLMs handle ~600-line
    # roles comfortably. Trim enhanced_fields/source noise that doesn't help review.
    trimmed = {k: v for k, v in role_data.items()}
    meta = dict(trimmed.get("meta", {}))
    meta.pop("source", None)
    trimmed["meta"] = meta

    yaml_text = yaml.safe_dump(trimmed, allow_unicode=True, sort_keys=False, width=100)
    role_id = role_data.get("meta", {}).get("role_id", "<unknown>")
    return (
        f"Review the following role YAML (role_id: {role_id}). Output JSON only.\n\n"
        f"```yaml\n{yaml_text}\n```"
    )


def parse_review_response(text: str) -> ReviewRecord:
    """Extract a ReviewRecord from an LLM response, tolerating code fences."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ReviewParseError("No JSON object found in review response")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as e:
        raise ReviewParseError(f"Review response was not valid JSON: {e}")

    verdict = data.get("verdict", "").strip()
    if verdict not in VALID_VERDICTS:
        raise ReviewParseError(
            f"Invalid verdict '{verdict}', must be one of {VALID_VERDICTS}"
        )

    try:
        score = int(data.get("score", 0))
    except (TypeError, ValueError):
        raise ReviewParseError("Review 'score' must be an integer")
    if not 1 <= score <= 5:
        raise ReviewParseError(f"Review 'score' {score} out of range 1-5")

    def _as_str_list(key):
        val = data.get(key, [])
        if val is None:
            return []
        if not isinstance(val, list):
            raise ReviewParseError(f"Review '{key}' must be a list")
        return [str(x) for x in val]

    return ReviewRecord(
        verdict=verdict,
        score=score,
        strengths=_as_str_list("strengths"),
        issues=_as_str_list("issues"),
        fix_hints=_as_str_list("fix_hints"),
    )


class Reviewer:
    """Build review prompts, optionally run them via Anthropic or Ollama, and
    attach the resulting record to a role via meta.review.
    """

    def __init__(self, role_manager, anthropic_api_key: Optional[str] = None,
                 model: str = "claude-opus-4-7", backend: str = "anthropic",
                 ollama_url: str = "http://localhost:11434"):
        self.rm = role_manager
        self._api_key = anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model
        self.backend = backend
        self.ollama_url = ollama_url.rstrip("/")

    # ─── prompt building ───────────────────────────────────────────────────

    def build_prompt(self, role_id: str) -> dict:
        role = self.rm.get_role(role_id, version="latest")
        return {
            "role_id": role_id,
            "system": REVIEW_SYSTEM_PROMPT,
            "user": build_user_prompt(role.to_dict()),
        }

    # ─── live LLM call ─────────────────────────────────────────────────────

    def run_live(self, role_id: str) -> ReviewRecord:
        if self.backend == "ollama":
            return self._run_ollama(role_id)
        return self._run_anthropic(role_id)

    def _run_anthropic(self, role_id: str) -> ReviewRecord:
        if not self._api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set — use build_prompt() for offline review"
            )
        try:
            from anthropic import Anthropic
        except ImportError as e:
            raise RuntimeError(
                "anthropic SDK not installed. `pip install anthropic` or run "
                "review in offline mode via `review prompt`."
            ) from e

        prompt = self.build_prompt(role_id)
        client = Anthropic(api_key=self._api_key)
        response = client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=prompt["system"],
            messages=[{"role": "user", "content": prompt["user"]}],
        )
        text = "".join(
            block.text for block in response.content if hasattr(block, "text")
        )
        record = parse_review_response(text)
        record.reviewer_model = self.model
        record.reviewed_at = _now_utc()
        return record

    def _run_ollama(self, role_id: str) -> ReviewRecord:
        import urllib.request
        import urllib.error

        prompt = self.build_prompt(role_id)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": prompt["system"]},
                {"role": "user", "content": prompt["user"]},
            ],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.2},
        }
        req = urllib.request.Request(
            f"{self.ollama_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        # Bypass system proxy — Ollama is local and our :7897 proxy would intercept.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(req, timeout=600) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise RuntimeError(f"Ollama request failed at {self.ollama_url}: {e}") from e

        text = body.get("message", {}).get("content", "")
        if not text:
            raise RuntimeError(f"Ollama returned empty content: {body}")
        record = parse_review_response(text)
        record.reviewer_model = f"ollama/{self.model}"
        record.reviewed_at = _now_utc()
        return record

    # ─── record attachment ─────────────────────────────────────────────────

    def attach_record(self, role_id: str, record: ReviewRecord) -> None:
        """Write meta.review into the role's latest version YAML and refresh
        the registry checksum (Phase 2.5 invariant)."""
        from ..utils.path_utils import role_id_to_parts

        entry = self.rm.registry_store.get_entry(role_id)
        if not entry:
            raise ValueError(f"Role '{role_id}' not found in registry")

        group, role_name = role_id_to_parts(role_id)
        latest = entry["latest_version"]
        data = self.rm.role_store.read_role(group, role_name, latest)
        meta = data.setdefault("meta", {})
        if not record.reviewed_at:
            record.reviewed_at = _now_utc()
        meta["review"] = record.to_dict()
        self.rm.role_store.write_role(group, role_name, latest, data)

        self.rm._refresh_version_checksum(entry, latest)
        entry["meta"]["updated_at"] = _now_utc()
        self.rm.registry_store.put_entry(role_id, entry)

    # ─── attach from manual verdict ────────────────────────────────────────

    def attach_manual(
        self,
        role_id: str,
        verdict: str,
        score: int,
        strengths: list = None,
        issues: list = None,
        fix_hints: list = None,
        reviewer_model: str = "human",
    ) -> ReviewRecord:
        if verdict not in VALID_VERDICTS:
            raise ValueError(f"verdict must be one of {VALID_VERDICTS}")
        if not 1 <= int(score) <= 5:
            raise ValueError("score must be in 1..5")
        record = ReviewRecord(
            verdict=verdict,
            score=int(score),
            strengths=list(strengths or []),
            issues=list(issues or []),
            fix_hints=list(fix_hints or []),
            reviewer_model=reviewer_model,
            reviewed_at=_now_utc(),
        )
        self.attach_record(role_id, record)
        return record


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ─── shared helpers for gate plumbing ─────────────────────────────────────────

def get_review_record(role_data: dict) -> Optional[ReviewRecord]:
    raw = (role_data.get("meta") or {}).get("review")
    if not raw:
        return None
    return ReviewRecord.from_dict(raw)

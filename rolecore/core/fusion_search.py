from dataclasses import dataclass
from typing import Optional

from ..models.registry_entry import RegistryEntry
from ..storage.registry_store import RegistryStore


JOB_GROUPS = frozenset({
    "academic", "ecommerce", "engineering", "game_development",
    "marketing", "paid_media", "product", "project_management",
    "sales", "spatial_computing", "specialized", "strategy",
    "support", "testing",
})

TECH_GROUPS = frozenset({
    "language", "framework", "database", "data_ml",
    "infrastructure", "integration", "tooling",
})

SPECIALTY_GROUPS = frozenset({
    "core_dev", "language_specialist", "infra_ops", "quality_security",
    "data_ai", "dev_exp", "specialized_v", "biz_product",
    "meta_orchestration", "research",
})

_AXIS_ORDER = ("job", "tech", "specialty")

_AXIS_OF_GROUP = {}
for g in JOB_GROUPS:
    _AXIS_OF_GROUP[g] = "job"
for g in TECH_GROUPS:
    _AXIS_OF_GROUP[g] = "tech"
for g in SPECIALTY_GROUPS:
    _AXIS_OF_GROUP[g] = "specialty"


FIELD_WEIGHTS = {
    "name_cn": 4.0,
    "name_en": 3.0,
    "domain": 2.0,
    "tags": 1.5,
    "role_id_tail": 1.0,
}


@dataclass
class FusionHit:
    entry: RegistryEntry
    axis: str
    score: float
    matched_fields: list

    def to_dict(self) -> dict:
        return {
            "role_id": self.entry.role_id,
            "name_cn": self.entry.name_cn,
            "name_en": self.entry.name_en,
            "group": self.entry.group,
            "axis": self.axis,
            "score": round(self.score, 2),
            "matched_fields": self.matched_fields,
        }


def axis_of(group: str) -> Optional[str]:
    return _AXIS_OF_GROUP.get(group)


def tokenize_query(query: str) -> list:
    return [t for t in query.strip().lower().split() if t]


def _score_entry(entry_dict: dict, tokens: list) -> tuple:
    """Return (score, matched_fields) for a single registry entry against tokens."""
    score = 0.0
    matched = []

    name_cn = (entry_dict.get("name_cn") or "").lower()
    name_en = (entry_dict.get("name_en") or "").lower()
    domain = (entry_dict.get("domain") or "").lower()
    tags = [str(t).lower() for t in (entry_dict.get("tags") or [])]
    role_id = entry_dict.get("role_id", "")
    tail = role_id.split(".", 1)[1].lower() if "." in role_id else role_id.lower()

    for tok in tokens:
        hit_this_token = False
        if tok and tok in name_cn:
            score += FIELD_WEIGHTS["name_cn"]
            hit_this_token = True
            if "name_cn" not in matched:
                matched.append("name_cn")
        if tok and tok in name_en:
            score += FIELD_WEIGHTS["name_en"]
            hit_this_token = True
            if "name_en" not in matched:
                matched.append("name_en")
        if tok and tok in domain:
            score += FIELD_WEIGHTS["domain"]
            hit_this_token = True
            if "domain" not in matched:
                matched.append("domain")
        if tok and any(tok in t for t in tags):
            score += FIELD_WEIGHTS["tags"]
            hit_this_token = True
            if "tags" not in matched:
                matched.append("tags")
        if tok and tok in tail:
            score += FIELD_WEIGHTS["role_id_tail"]
            hit_this_token = True
            if "role_id_tail" not in matched:
                matched.append("role_id_tail")
        # Mild bonus for matching multiple tokens (coverage)
        if hit_this_token:
            score += 0.5

    return score, matched


class FusionSearchEngine:
    """Cross-axis (job / tech / specialty) recommendation engine over the role registry.

    Given a natural-language query, returns ranked candidates per axis plus a
    "triad" — one top pick from each axis that together cover the query.
    """

    def __init__(self, registry_store: RegistryStore):
        self.registry_store = registry_store

    def find(
        self,
        query: str,
        top_k_per_axis: int = 5,
        status_filter: str = "official",
        verdict_filter: Optional[str] = None,
    ) -> dict:
        tokens = tokenize_query(query)
        if not tokens:
            return {"query": query, "tokens": [], "job": [], "tech": [], "specialty": [], "triad": {}}

        hits_by_axis = {"job": [], "tech": [], "specialty": []}
        for entry_dict in self.registry_store.list_all_entries():
            entry_meta = entry_dict.get("meta") or {}
            status = entry_meta.get("status", "")
            if status_filter and status != status_filter:
                continue
            if verdict_filter:
                review = entry_meta.get("review") or {}
                if review.get("verdict") != verdict_filter:
                    continue
            group = entry_dict.get("group", "")
            axis = _AXIS_OF_GROUP.get(group)
            if not axis:
                continue
            score, matched = _score_entry(entry_dict, tokens)
            if score <= 0:
                continue
            hits_by_axis[axis].append(
                FusionHit(
                    entry=RegistryEntry.from_dict(entry_dict),
                    axis=axis,
                    score=score,
                    matched_fields=matched,
                )
            )

        # Sort by score desc, then prefer shorter role_id tail (more canonical),
        # then alphabetical for determinism.
        def _sort_key(h):
            tail = h.entry.role_id.split(".", 1)[1] if "." in h.entry.role_id else h.entry.role_id
            return (-h.score, len(tail), h.entry.role_id)

        for axis in hits_by_axis:
            hits_by_axis[axis].sort(key=_sort_key)

        top_per_axis = {
            axis: hits_by_axis[axis][:top_k_per_axis]
            for axis in _AXIS_ORDER
        }
        triad = {
            axis: (hits_by_axis[axis][0] if hits_by_axis[axis] else None)
            for axis in _AXIS_ORDER
        }

        return {
            "query": query,
            "tokens": tokens,
            "status_filter": status_filter,
            **top_per_axis,
            "triad": triad,
        }

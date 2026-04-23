from dataclasses import dataclass, field
from typing import Optional

# ─── Status lifecycle ─────────────────────────────────────────────────────────
# raw_imported → normalized → curated → official → archived
VALID_STATUSES = {"raw_imported", "normalized", "curated", "official", "archived"}

# Legacy values written by old code — mapped on read, never re-written
_LEGACY_STATUS_MAP = {
    "active":     "curated",
    "deprecated": "archived",
    "draft":      "raw_imported",
}


def normalize_status(s: str) -> str:
    """Translate legacy status strings to the canonical five-level vocabulary."""
    return _LEGACY_STATUS_MAP.get(s, s)


@dataclass
class RoleIdentity:
    name_cn: str
    name_en: str
    domain: str
    positioning: str

    @classmethod
    def from_dict(cls, d: dict) -> "RoleIdentity":
        return cls(
            name_cn=d["name_cn"],
            name_en=d["name_en"],
            domain=d["domain"],
            positioning=d["positioning"],
        )

    def to_dict(self) -> dict:
        return {
            "name_cn": self.name_cn,
            "name_en": self.name_en,
            "domain": self.domain,
            "positioning": self.positioning,
        }


@dataclass
class RoleMission:
    summary: str
    core_accountability: list

    @classmethod
    def from_dict(cls, d: dict) -> "RoleMission":
        return cls(
            summary=d["summary"],
            core_accountability=d["core_accountability"],
        )

    def to_dict(self) -> dict:
        return {
            "summary": self.summary,
            "core_accountability": self.core_accountability,
        }


@dataclass
class RoleBoundaries:
    can_do: list
    cannot_do: list
    escalate_when: list

    @classmethod
    def from_dict(cls, d: dict) -> "RoleBoundaries":
        return cls(
            can_do=d["can_do"],
            cannot_do=d["cannot_do"],
            escalate_when=d["escalate_when"],
        )

    def to_dict(self) -> dict:
        return {
            "can_do": self.can_do,
            "cannot_do": self.cannot_do,
            "escalate_when": self.escalate_when,
        }


@dataclass
class RoleIO:
    inputs: list
    outputs: list

    @classmethod
    def from_dict(cls, d: dict) -> "RoleIO":
        return cls(inputs=d["inputs"], outputs=d["outputs"])

    def to_dict(self) -> dict:
        return {"inputs": self.inputs, "outputs": self.outputs}


@dataclass
class RoleBehavior:
    communication_style: str
    risk_preference: str
    decision_approach: str
    collaboration_mode: str

    @classmethod
    def from_dict(cls, d: dict) -> "RoleBehavior":
        return cls(
            communication_style=d["communication_style"],
            risk_preference=d["risk_preference"],
            decision_approach=d["decision_approach"],
            collaboration_mode=d["collaboration_mode"],
        )

    def to_dict(self) -> dict:
        return {
            "communication_style": self.communication_style,
            "risk_preference": self.risk_preference,
            "decision_approach": self.decision_approach,
            "collaboration_mode": self.collaboration_mode,
        }


@dataclass
class RoleWorkflow:
    name: str
    steps: list

    @classmethod
    def from_dict(cls, d: dict) -> "RoleWorkflow":
        return cls(name=d["name"], steps=d["steps"])

    def to_dict(self) -> dict:
        return {"name": self.name, "steps": self.steps}


@dataclass
class RoleCapabilities:
    tools: list
    knowledge: list
    context_requirements: list
    runtime_conditions: list

    @classmethod
    def from_dict(cls, d: dict) -> "RoleCapabilities":
        return cls(
            tools=d["tools"],
            knowledge=d["knowledge"],
            context_requirements=d["context_requirements"],
            runtime_conditions=d["runtime_conditions"],
        )

    def to_dict(self) -> dict:
        return {
            "tools": self.tools,
            "knowledge": self.knowledge,
            "context_requirements": self.context_requirements,
            "runtime_conditions": self.runtime_conditions,
        }


@dataclass
class RoleEvaluation:
    metrics: list
    success_criteria: list

    @classmethod
    def from_dict(cls, d: dict) -> "RoleEvaluation":
        return cls(
            metrics=d["metrics"],
            success_criteria=d["success_criteria"],
        )

    def to_dict(self) -> dict:
        return {
            "metrics": self.metrics,
            "success_criteria": self.success_criteria,
        }


@dataclass
class RoleMeta:
    role_id: str
    version: str
    group: str
    tags: list
    status: str
    created_at: str = ""
    updated_at: str = ""
    author: str = "system"
    description: str = ""
    # Source provenance — populated for upstream-imported roles
    source: dict = field(default_factory=dict)
    # Optional quality review record (set via the reviewer workflow)
    review: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "RoleMeta":
        raw_status = d.get("status", "raw_imported")
        return cls(
            role_id=d["role_id"],
            version=str(d["version"]),
            group=d["group"],
            tags=d.get("tags", []),
            status=normalize_status(raw_status),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            author=d.get("author", "system"),
            description=d.get("description", ""),
            source=d.get("source", {}),
            review=d.get("review", {}),
        )

    def to_dict(self) -> dict:
        d = {
            "role_id": self.role_id,
            "version": self.version,
            "group": self.group,
            "tags": self.tags,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "author": self.author,
            "description": self.description,
        }
        if self.source:
            d["source"] = self.source
        if self.review:
            d["review"] = self.review
        return d


@dataclass
class RoleAsset:
    meta: RoleMeta
    identity: RoleIdentity
    mission: RoleMission
    boundaries: RoleBoundaries
    io: RoleIO
    behavior: RoleBehavior
    workflows: list
    capabilities: RoleCapabilities
    evaluation: RoleEvaluation

    @classmethod
    def from_dict(cls, d: dict) -> "RoleAsset":
        return cls(
            meta=RoleMeta.from_dict(d["meta"]),
            identity=RoleIdentity.from_dict(d["identity"]),
            mission=RoleMission.from_dict(d["mission"]),
            boundaries=RoleBoundaries.from_dict(d["boundaries"]),
            io=RoleIO.from_dict(d["io"]),
            behavior=RoleBehavior.from_dict(d["behavior"]),
            workflows=[RoleWorkflow.from_dict(w) for w in d.get("workflows", [])],
            capabilities=RoleCapabilities.from_dict(d["capabilities"]),
            evaluation=RoleEvaluation.from_dict(d["evaluation"]),
        )

    def to_dict(self) -> dict:
        return {
            "meta": self.meta.to_dict(),
            "identity": self.identity.to_dict(),
            "mission": self.mission.to_dict(),
            "boundaries": self.boundaries.to_dict(),
            "io": self.io.to_dict(),
            "behavior": self.behavior.to_dict(),
            "workflows": [w.to_dict() for w in self.workflows],
            "capabilities": self.capabilities.to_dict(),
            "evaluation": self.evaluation.to_dict(),
        }

    @property
    def role_id(self) -> str:
        return self.meta.role_id

    @property
    def version(self) -> str:
        return self.meta.version

"""Shared pytest fixtures for rolecore test suite."""

import os
import sys

import pytest

# Ensure project root is on sys.path so `import rolecore` works.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


@pytest.fixture
def project_root():
    return _PROJECT_ROOT


@pytest.fixture
def upstream_dir(project_root):
    return os.path.join(project_root, "upstream")


@pytest.fixture
def valid_role_data():
    """A complete, schema-valid role payload for schema / gate tests."""
    return {
        "meta": {
            "role_id": "engineering.test_role",
            "version": "1",
            "group": "engineering",
            "tags": ["engineering", "test"],
            "status": "official",
            "description": "Test fixture",
        },
        "identity": {
            "name_cn": "测试角色",
            "name_en": "Test Role",
            "domain": "software_engineering",
            "positioning": (
                "A thorough senior engineer who designs, implements, and reviews "
                "production backend services with strict quality and security standards."
            ),
        },
        "mission": {
            "summary": (
                "Deliver production-ready backend services with rigorous testing, "
                "clean architecture, and measurable reliability targets across the "
                "entire lifecycle of the system."
            ),
            "core_accountability": [
                "Own backend service quality from design through production operations",
                "Drive incident response and post-mortem learning for reliability issues",
                "Mentor teammates and maintain long-term architectural coherence",
            ],
        },
        "boundaries": {
            "can_do": [
                "Design distributed backend architectures with scaling requirements",
                "Review security posture of service-to-service authentication",
                "Lead root-cause analysis for production outages and regressions",
            ],
            "cannot_do": [
                "Make product strategy calls without stakeholder alignment",
            ],
            "escalate_when": [
                "Changes impact cross-team SLOs or require budget decisions",
            ],
        },
        "io": {
            "inputs": ["Requirements doc", "Current system topology"],
            "outputs": ["Design doc", "Reviewed PR"],
        },
        "behavior": {
            "communication_style": "Direct, evidence-based, and structured; leads with tradeoffs.",
            "risk_preference": "Cautious when data is thin; decisive once verified.",
            "decision_approach": "Tradeoff matrix grounded in observed data.",
            "collaboration_mode": "Consult first, commit, then broadcast.",
        },
        "workflows": [
            {
                "name": "standard_review",
                "steps": [
                    "Read the context docs and relevant code paths carefully",
                    "Identify the top three risks and verify them against production data",
                    "Produce a written review with concrete, actionable recommendations",
                ],
            }
        ],
        "capabilities": {
            "tools": ["git", "kubectl"],
            "knowledge": ["distributed-systems", "observability"],
            "context_requirements": ["recent production metrics"],
            "runtime_conditions": ["staging environment available"],
        },
        "evaluation": {
            "metrics": [
                "Mean time to detect critical service regressions",
                "Percentage of designs reviewed before implementation",
            ],
            "success_criteria": [
                "All production changes are covered by observability dashboards",
                "No SEV-1 incidents attributable to reviewed designs in 90 days",
            ],
        },
    }

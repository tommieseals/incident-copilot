"""
Fix Suggester - Generates remediation suggestions based on analysis.

Provides:
- Immediate mitigation commands
- Permanent fix recommendations
- Rollback procedures
- Prevention measures
"""

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class FixCategory(Enum):
    """Categories of fixes."""
    IMMEDIATE = "immediate"
    ROLLBACK = "rollback"
    CONFIGURATION = "config"
    SCALING = "scaling"
    INFRASTRUCTURE = "infra"
    CODE = "code"
    INVESTIGATION = "investigate"


class RiskLevel(Enum):
    """Risk level of applying a fix."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SuggestedFix:
    """A suggested fix for the incident."""
    title: str
    description: str
    category: FixCategory
    risk: RiskLevel
    commands: list[str]
    impact: str
    prerequisites: list[str] = field(default_factory=list)
    rollback_commands: list[str] = field(default_factory=list)
    estimated_time: str = "< 5 minutes"
    confidence: float = 0.8

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "description": self.description,
            "category": self.category.value,
            "risk": self.risk.value,
            "commands": self.commands,
            "impact": self.impact,
            "prerequisites": self.prerequisites,
            "rollback_commands": self.rollback_commands,
            "estimated_time": self.estimated_time,
            "confidence": self.confidence,
        }


class FixSuggester:
    """Generates fix suggestions based on incident analysis."""

    PLAYBOOKS = {
        "oom_kill": [
            SuggestedFix(
                title="Restart affected pods",
                description="Restart pods that were OOM killed to restore service",
                category=FixCategory.IMMEDIATE,
                risk=RiskLevel.LOW,
                commands=["kubectl rollout restart deployment/{deployment} -n {namespace}"],
                impact="Brief service interruption during rolling restart",
                estimated_time="2-3 minutes",
            ),
            SuggestedFix(
                title="Increase memory limits",
                description="Increase memory limits to prevent future OOM kills",
                category=FixCategory.CONFIGURATION,
                risk=RiskLevel.MEDIUM,
                commands=["kubectl set resources deployment/{deployment} -n {namespace} --limits=memory={new_limit}"],
                impact="Pods will be recreated with new limits",
                prerequisites=["Verify cluster has sufficient memory"],
            ),
        ],
        "connection_pool": [
            SuggestedFix(
                title="Restart application pods",
                description="Restart to reset connection pool state",
                category=FixCategory.IMMEDIATE,
                risk=RiskLevel.LOW,
                commands=["kubectl rollout restart deployment/{deployment} -n {namespace}"],
                impact="Connections will be re-established",
                estimated_time="1-2 minutes",
            ),
            SuggestedFix(
                title="Increase connection pool size",
                description="Increase maximum connections to handle load",
                category=FixCategory.CONFIGURATION,
                risk=RiskLevel.MEDIUM,
                commands=["kubectl set env deployment/{deployment} DB_POOL_SIZE={new_pool_size} -n {namespace}"],
                impact="Higher database load, verify DB can handle it",
                prerequisites=["Check database max_connections setting"],
            ),
        ],
        "timeout": [
            SuggestedFix(
                title="Scale up deployment",
                description="Add more replicas to handle load",
                category=FixCategory.SCALING,
                risk=RiskLevel.LOW,
                commands=["kubectl scale deployment/{deployment} --replicas={new_replicas} -n {namespace}"],
                impact="Additional pods will be created",
            ),
        ],
        "crash_loop": [
            SuggestedFix(
                title="Check pod logs",
                description="Review crash logs for root cause",
                category=FixCategory.INVESTIGATION,
                risk=RiskLevel.LOW,
                commands=["kubectl logs {pod} --previous -n {namespace}", "kubectl describe pod {pod} -n {namespace}"],
                impact="None - diagnostic only",
            ),
            SuggestedFix(
                title="Rollback deployment",
                description="Rollback to previous working version",
                category=FixCategory.ROLLBACK,
                risk=RiskLevel.MEDIUM,
                commands=["kubectl rollout undo deployment/{deployment} -n {namespace}"],
                impact="Application will revert to previous version",
            ),
        ],
    }

    def __init__(self, config: dict):
        self.config = config
        self.custom_playbooks = config.get("playbooks", {})

    async def suggest_fixes(self, incident: Any, analysis: dict) -> list[dict]:
        """Generate fix suggestions based on incident analysis."""
        suggestions = []
        root_cause = analysis.get("root_cause", "").lower()
        
        for pattern_name, playbook in self.PLAYBOOKS.items():
            if self._matches_pattern(pattern_name, root_cause, analysis):
                logger.info(f"Matched playbook: {pattern_name}")
                populated = self._populate_playbook(playbook, incident, analysis)
                suggestions.extend(populated)
        
        if not suggestions:
            suggestions = self._generic_suggestions(incident, analysis)
        
        suggestions.sort(key=lambda x: (list(RiskLevel).index(RiskLevel(x["risk"])), -x.get("confidence", 0.5)))
        return suggestions[:5]

    def _matches_pattern(self, pattern_name: str, root_cause: str, analysis: dict) -> bool:
        patterns = {
            "oom_kill": ["oom", "out of memory", "memory exhaust", "killed"],
            "connection_pool": ["connection pool", "pool exhaust", "no connections"],
            "timeout": ["timeout", "timed out", "deadline", "slow response"],
            "crash_loop": ["crash", "crashloop", "restarting", "exit code"],
        }
        for keyword in patterns.get(pattern_name, []):
            if keyword in root_cause:
                return True
        return False

    def _populate_playbook(self, playbook: list[SuggestedFix], incident: Any, analysis: dict) -> list[dict]:
        populated = []
        labels = getattr(incident, "labels", {})
        context = {
            "deployment": labels.get("deployment", labels.get("app", "YOUR_DEPLOYMENT")),
            "namespace": labels.get("namespace", "default"),
            "pod": labels.get("pod", "YOUR_POD"),
            "new_limit": "2Gi",
            "new_pool_size": "100",
            "new_replicas": "5",
        }
        
        for fix in playbook:
            populated_commands = []
            for cmd in fix.commands:
                populated_cmd = cmd
                for key, value in context.items():
                    populated_cmd = populated_cmd.replace(f"{{{key}}}", str(value))
                populated_commands.append(populated_cmd)
            populated.append({**fix.to_dict(), "commands": populated_commands})
        return populated

    def _generic_suggestions(self, incident: Any, analysis: dict) -> list[dict]:
        labels = getattr(incident, "labels", {})
        deployment = labels.get("deployment", labels.get("app", "YOUR_DEPLOYMENT"))
        namespace = labels.get("namespace", "default")
        
        return [
            {
                "title": "Gather more diagnostics",
                "description": "Collect additional information to diagnose the issue",
                "category": "investigate",
                "risk": "low",
                "commands": [
                    f"kubectl logs -l app={deployment} --tail=500 -n {namespace}",
                    f"kubectl describe pods -l app={deployment} -n {namespace}",
                ],
                "impact": "None - diagnostic only",
                "estimated_time": "5 minutes",
                "confidence": 0.9,
            },
            {
                "title": "Restart affected service",
                "description": "Rolling restart to clear potentially corrupted state",
                "category": "immediate",
                "risk": "low",
                "commands": [f"kubectl rollout restart deployment/{deployment} -n {namespace}"],
                "impact": "Brief service interruption during rolling restart",
                "estimated_time": "2-3 minutes",
                "confidence": 0.6,
            },
            {
                "title": "Rollback to previous version",
                "description": "Revert to the last known good deployment",
                "category": "rollback",
                "risk": "medium",
                "commands": [f"kubectl rollout undo deployment/{deployment} -n {namespace}"],
                "impact": "Application will revert to previous version",
                "estimated_time": "2-3 minutes",
                "confidence": 0.5,
            },
        ]

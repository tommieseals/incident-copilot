"""
Notifier - Multi-channel notification system.

Supports:
- Slack
- Microsoft Teams
- PagerDuty
- Email (SMTP)
- Webhooks
"""

import json
import logging
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SlackNotifier:
    """Send notifications to Slack."""

    def __init__(self, config: dict):
        self.webhook_url = config.get("webhook_url")
        self.channel = config.get("channel", "#incidents")
        self.username = config.get("username", "Incident Copilot")
        self.icon_emoji = config.get("icon_emoji", ":rotating_light:")

    async def send(self, message: dict) -> bool:
        if not self.webhook_url:
            logger.warning("Slack webhook URL not configured")
            return False
        
        try:
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=message) as resp:
                    return resp.status == 200
        except ImportError:
            import requests
            resp = requests.post(self.webhook_url, json=message)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Slack notification failed: {e}")
            return False

    def format_incident_triggered(self, incident: Any) -> dict:
        severity_colors = {
            "critical": "#FF0000",
            "high": "#FF6B00",
            "medium": "#FFB800",
            "low": "#00B8FF",
            "info": "#808080",
        }
        
        severity = incident.severity.value if hasattr(incident.severity, "value") else str(incident.severity)
        color = severity_colors.get(severity.lower(), "#808080")
        
        return {
            "username": self.username,
            "icon_emoji": self.icon_emoji,
            "channel": self.channel,
            "attachments": [{
                "color": color,
                "title": f":rotating_light: Incident Detected: {incident.title}",
                "text": incident.description,
                "fields": [
                    {"title": "Severity", "value": severity.upper(), "short": True},
                    {"title": "Source", "value": incident.source, "short": True},
                    {"title": "ID", "value": incident.id, "short": True},
                    {"title": "Status", "value": "Analyzing...", "short": True},
                ],
                "footer": "Incident Copilot",
                "ts": int(datetime.utcnow().timestamp()),
            }],
        }

    def format_analysis_complete(self, incident: Any) -> dict:
        analysis = getattr(incident, "analysis", {}) or {}
        fixes = getattr(incident, "suggested_fixes", []) or []
        
        fix_text = "\n".join([
            f"• *{f.get('title', 'Unknown')}* ({f.get('risk', 'unknown')} risk)"
            for f in fixes[:3]
        ]) or "No suggestions available"
        
        return {
            "username": self.username,
            "icon_emoji": ":mag:",
            "channel": self.channel,
            "attachments": [{
                "color": "#00B8FF",
                "title": f":mag: Analysis Complete: {incident.title}",
                "fields": [
                    {
                        "title": "Root Cause",
                        "value": analysis.get("root_cause", "Unknown")[:500],
                        "short": False,
                    },
                    {
                        "title": "Confidence",
                        "value": f"{analysis.get('confidence', 0)}%",
                        "short": True,
                    },
                    {
                        "title": "Suggested Fixes",
                        "value": fix_text,
                        "short": False,
                    },
                ],
                "footer": f"Incident ID: {incident.id}",
            }],
        }

    def format_incident_resolved(self, incident: Any) -> dict:
        mttr = incident.mttr_seconds if hasattr(incident, "mttr_seconds") else None
        mttr_text = f"{mttr // 60}m {mttr % 60}s" if mttr else "Unknown"
        
        return {
            "username": self.username,
            "icon_emoji": ":white_check_mark:",
            "channel": self.channel,
            "attachments": [{
                "color": "#00FF00",
                "title": f":white_check_mark: Incident Resolved: {incident.title}",
                "fields": [
                    {"title": "Resolution Time (MTTR)", "value": mttr_text, "short": True},
                    {"title": "ID", "value": incident.id, "short": True},
                ],
                "footer": "Incident Copilot",
            }],
        }


class TeamsNotifier:
    """Send notifications to Microsoft Teams."""

    def __init__(self, config: dict):
        self.webhook_url = config.get("webhook_url")

    async def send(self, message: dict) -> bool:
        if not self.webhook_url:
            logger.warning("Teams webhook URL not configured")
            return False
        
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=message) as resp:
                    return resp.status == 200
        except Exception as e:
            logger.error(f"Teams notification failed: {e}")
            return False

    def format_incident_triggered(self, incident: Any) -> dict:
        severity = incident.severity.value if hasattr(incident.severity, "value") else str(incident.severity)
        
        return {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": "FF0000" if severity == "critical" else "FF6B00",
            "summary": f"Incident: {incident.title}",
            "sections": [{
                "activityTitle": f"🚨 Incident Detected: {incident.title}",
                "facts": [
                    {"name": "Severity", "value": severity.upper()},
                    {"name": "Source", "value": incident.source},
                    {"name": "ID", "value": incident.id},
                ],
                "markdown": True,
            }],
        }


class Notifier:
    """Main notification orchestrator."""

    def __init__(self, config: dict):
        self.config = config
        self.slack = SlackNotifier(config.get("slack", {})) if config.get("slack") else None
        self.teams = TeamsNotifier(config.get("teams", {})) if config.get("teams") else None
        self.enabled = config.get("enabled", True)

    async def send_incident_triggered(self, incident: Any) -> None:
        if not self.enabled:
            return
        
        logger.info(f"Sending incident triggered notification for {incident.id}")
        
        if self.slack:
            message = self.slack.format_incident_triggered(incident)
            await self.slack.send(message)
        
        if self.teams:
            message = self.teams.format_incident_triggered(incident)
            await self.teams.send(message)

    async def send_analysis_complete(self, incident: Any) -> None:
        if not self.enabled:
            return
        
        logger.info(f"Sending analysis complete notification for {incident.id}")
        
        if self.slack:
            message = self.slack.format_analysis_complete(incident)
            await self.slack.send(message)

    async def send_incident_resolved(self, incident: Any) -> None:
        if not self.enabled:
            return
        
        logger.info(f"Sending incident resolved notification for {incident.id}")
        
        if self.slack:
            message = self.slack.format_incident_resolved(incident)
            await self.slack.send(message)

    async def send_error(self, incident: Any, error: str) -> None:
        if not self.enabled:
            return
        
        logger.error(f"Sending error notification for {incident.id}: {error}")
        
        if self.slack:
            message = {
                "channel": self.slack.channel,
                "text": f":x: Error processing incident {incident.id}: {error}",
            }
            await self.slack.send(message)

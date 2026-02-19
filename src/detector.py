" Incident Detector - Webhook receiver and incident detection engine. Supports: - PagerDuty webhooks - Prometheus AlertManager - Datadog webhooks - Grafana alerts - Custom REST API "

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

from aiohttp import web

from .gatherer import LogGatherer
from .analyzer import IncidentAnalyzer
from .responder import FixSuggester
from .postmortem import PostMortemGenerator
from .notifier import Notifier
from .storage import IncidentStorage

logger = logging.getLogger(__name__)


class IncidentSeverity(Enum):
    "Incident severity levels."
    CRITICAL = critical
    HIGH = high
    MEDIUM = medium
    LOW = low
    INFO = info


class IncidentStatus(Enum):
    "Incident lifecycle status."
    TRIGGERED = triggered
    ACKNOWLEDGED = acknowledged
    ANALYZING = analyzing
    MITIGATING = mitigating
    RESOLVED = resolved


@dataclass
class Incident:
    "Represents a single incident."
    id: str
    title: str
    description: str
    severity: IncidentSeverity
    source: str
    status: IncidentStatus = IncidentStatus.TRIGGERED
    triggered_at: datetime = field(default_factory=datetime.utcnow)
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    labels: dict[str, str] = field(default_factory=dict)
    raw_payload: dict[str, Any] = field(default_factory=dict)
    logs: list[str] = field(default_factory=list)
    analysis: Optional[dict] = None
    suggested_fixes: list[dict] = field(default_factory=list)
    postmortem: Optional[str] = None

    def to_dict(self) -> dict:
        "Serialize incident to dictionary."
        return {
            id: self.id,
            title: self.title,
            description: self.description,
            severity: self.severity.value,
            source: self.source,
            status: self.status.value,
            triggered_at: self.triggered_at.isoformat(),
            acknowledged_at: self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            resolved_at: self.resolved_at.isoformat() if self.resolved_at else None,
            labels: self.labels,
            mttr_seconds: self.mttr_seconds,
        }

    @property
    def mttr_seconds(self) -> Optional[int]:
        "Calculate Mean Time To Resolution in seconds."
        if self.resolved_at and self.triggered_at:
            return int((self.resolved_at - self.triggered_at).total_seconds())
        return None


class WebhookParser:
    "Parse incoming webhooks from various monitoring systems."

    @staticmethod
    def parse_pagerduty(payload: dict) -> Incident:
        "Parse PagerDuty webhook payload."
        event = payload.get(event, {})
        incident_data = event.get(data, {})
        
        severity_map = {
            critical: IncidentSeverity.CRITICAL,
            error: IncidentSeverity.HIGH,
            warning: IncidentSeverity.MEDIUM,
            info: IncidentSeverity.LOW,
        }
        
        return Incident(
            id=fpd- unknown)},
            title=incident_data.get(title, Unknown PagerDuty Incident),
            description=incident_data.get(description, "),
            severity=severity_map.get(
                incident_data.get(urgency, info),
                IncidentSeverity.MEDIUM
            ),
            source=pagerduty,
            labels={
                service: incident_data.get(service, {}).get(name, unknown),
                escalation_policy: incident_data.get(escalation_policy, {}).get(name, "),
            },
            raw_payload=payload,
        )

    @staticmethod
    def parse_prometheus(payload: dict) -> Incident:
        "Parse Prometheus AlertManager webhook payload."
        alerts = payload.get(alerts, [])
        if not alerts:
            raise ValueError(No alerts in Prometheus payload)
        
        alert = alerts[0]  # Process first alert
        labels = alert.get(labels, {})
        annotations = alert.get(annotations, {})
        
        severity_map = {
            critical: IncidentSeverity.CRITICAL,
            warning: IncidentSeverity.MEDIUM,
            info: IncidentSeverity.LOW,
        }
        
        alert_name = labels.get(alertname, UnknownAlert)
        fingerprint = alert.get(fingerprint, hashlib.md5(
            json.dumps(labels, sort_keys=True).encode()
        ).hexdigest()[:12])
        
        return Incident(
            id=fprom-fingerprint,
            title=f[ warning).upper()}] alert_name,
            description=annotations.get(description, annotations.get(summary, ")),
            severity=severity_map.get(
                labels.get(severity, warning),
                IncidentSeverity.MEDIUM
            ),
            source=prometheus,
            labels=labels,
            raw_payload=payload,
        )

    @staticmethod
    def parse_datadog(payload: dict) -> Incident:
        "Parse Datadog webhook payload."
        severity_map = {
            1: IncidentSeverity.INFO,
            2: IncidentSeverity.LOW,
            3: IncidentSeverity.MEDIUM,
            4: IncidentSeverity.HIGH,
            5: IncidentSeverity.CRITICAL,
        }
        
        return Incident(
            id=fdd- unknown)},
            title=payload.get(title, Unknown Datadog Alert),
            description=payload.get(body, "),
            severity=severity_map.get(
                str(payload.get(priority, 3)),
                IncidentSeverity.MEDIUM
            ),
            source=datadog,
            labels={
                host: payload.get(host, unknown),
                scope: payload.get(scope, "),
            },
            raw_payload=payload,
        )

    @staticmethod
    def parse_grafana(payload: dict) -> Incident:
        "Parse Grafana alert webhook payload."
        alerts = payload.get(alerts, [])
        alert = alerts[0] if alerts else {}
        
        severity_map = {
            alerting: IncidentSeverity.HIGH,
            no_data: IncidentSeverity.MEDIUM,
            ok: IncidentSeverity.INFO,
        }
        
        return Incident(
            id=fgf- unknown)},
            title=payload.get(title, alert.get(labels, {}).get(alertname, Unknown)),
            description=payload.get(message, "),
            severity=severity_map.get(
                payload.get(state, alerting),
                IncidentSeverity.MEDIUM
            ),
            source=grafana,
            labels=alert.get(labels, {}),
            raw_payload=payload,
        )

    @staticmethod
    def parse_generic(payload: dict) -> Incident:
        "Parse generic/custom webhook payload."
        return Incident(
            id=fcustom- datetime.utcnow().strftime(%Y%m%d%H%M%S))},
            title=payload.get(title, payload.get(name, Unknown Incident)),
            description=payload.get(description, payload.get(message, ")),
            severity=IncidentSeverity(
                payload.get(severity, medium).lower()
            ),
            source=custom,
            labels=payload.get(labels, {}),
            raw_payload=payload,
        )


class IncidentDetector:
    "Main incident detection and processing engine."

    def __init__(self, config: dict):
        "Initialize detector with configuration."
        self.config = config
        self.gatherer = LogGatherer(config.get(log_sources, []))
        self.analyzer = IncidentAnalyzer(config.get(ai, {}))
        self.suggester = FixSuggester(config.get(ai, {}))
        self.postmortem_gen = PostMortemGenerator(config.get(templates, {}))
        self.notifier = Notifier(config.get(notifications, {}))
        self.storage = IncidentStorage(config.get(storage, {}))
        
        self.webhook_parsers: dict[str, Callable] = {
            pagerduty: WebhookParser.parse_pagerduty,
            prometheus: WebhookParser.parse_prometheus,
            alertmanager: WebhookParser.parse_prometheus,
            datadog: WebhookParser.parse_datadog,
            grafana: WebhookParser.parse_grafana,
            generic: WebhookParser.parse_generic,
        }
        
        self._active_incidents: dict[str, Incident] = {}

    async def process_webhook(self, source: str, payload: dict) -> Incident:
        "Process incoming webhook and trigger incident response."
        logger.info(fReceived webhook from source)
        
        # Parse webhook into incident
        parser = self.webhook_parsers.get(source, WebhookParser.parse_generic)
        incident = parser(payload)
        
        # Check for duplicate/existing incident
        if incident.id in self._active_incidents:
            logger.info(fUpdating existing incident incident.id)
            existing = self._active_incidents[incident.id]
            existing.raw_payload = payload
            return existing
        
        # Store and process new incident
        self._active_incidents[incident.id] = incident
        await self.storage.save_incident(incident)
        
        # Notify about new incident
        await self.notifier.send_incident_triggered(incident)
        
        # Start async processing pipeline
        asyncio.create_task(self._process_incident(incident))
        
        return incident

    async def _process_incident(self, incident: Incident):
        "Full incident processing pipeline."
        try:
            # Phase 1: Gather logs and context
            incident.status = IncidentStatus.ANALYZING
            logger.info(f[incident.id] Gathering logs and context...)
            
            incident.logs = await self.gatherer.gather_logs(
                incident=incident,
                time_range_minutes=self.config.get(gather_time_range, 60)
            )
            
            # Phase 2: AI Analysis
            logger.info(f[incident.id] Running AI analysis...)
            incident.analysis = await self.analyzer.analyze(
                incident=incident,
                logs=incident.logs
            )
            
            # Phase 3: Generate fix suggestions
            logger.info(f[incident.id] Generating fix suggestions...)
            incident.suggested_fixes = await self.suggester.suggest_fixes(
                incident=incident,
                analysis=incident.analysis
            )
            
            # Phase 4: Send analysis results
            await self.notifier.send_analysis_complete(incident)
            
            # Phase 5: Generate post-mortem draft
            logger.info(f[incident.id] Generating post-mortem draft...)
            incident.postmortem = await self.postmortem_gen.generate(incident)
            
            await self.storage.update_incident(incident)
            
        except Exception as e:
            logger.error(f[incident.id] Processing failed: e, exc_info=True)
            await self.notifier.send_error(incident, str(e))

    async def resolve_incident(self, incident_id: str) -> Optional[Incident]:
        "Mark an incident as resolved."
        if incident_id not in self._active_incidents:
            return None
        
        incident = self._active_incidents[incident_id]
        incident.status = IncidentStatus.RESOLVED
        incident.resolved_at = datetime.utcnow()
        
        await self.storage.update_incident(incident)
        await self.notifier.send_incident_resolved(incident)
        
        # Calculate and log MTTR
        if incident.mttr_seconds:
            minutes = incident.mttr_seconds // 60
            logger.info(f[incident_id] Resolved in minutesm  % 60}s)
        
        del self._active_incidents[incident_id]
        return incident

    def get_active_incidents(self) -> list[Incident]:
        "Get all currently active incidents."
        return list(self._active_incidents.values())


class IncidentServer:
    "HTTP server for receiving webhooks."

    def __init__(self, detector: IncidentDetector, config: dict):
        "Initialize server."
        self.detector = detector
        self.config = config
        self.app = web.Application()
        self._setup_routes()

    def _setup_routes(self):
        "Configure HTTP routes."
        self.app.router.add_post(/webhook/source, self._handle_webhook)
        self.app.router.add_post(/webhook, self._handle_generic_webhook)
        self.app.router.add_get(/health, self._health_check)
        self.app.router.add_get(/incidents, self._list_incidents)
        self.app.router.add_post(/incidents/id/resolve, self._resolve_incident)
        self.app.router.add_get(/incidents/id, self._get_incident)
        self.app.router.add_get(/stats, self._get_stats)

    async def _handle_webhook(self, request: web.Request) -> web.Response:
        "Handle incoming webhook from monitoring system."
        source = request.match_info[source]
        
        try:
            payload = await request.json()
        except json.JSONDecodeError:
            return web.json_response(
                {error: Invalid JSON payload},
                status=400
            )
        
        try:
            incident = await self.detector.process_webhook(source, payload)
            return web.json_response({
                status: accepted,
                incident_id: incident.id,
                message: fIncident incident.id is being processed
            })
        except Exception as e:
            logger.error(fWebhook processing error: e, exc_info=True)
            return web.json_response(
                {error: str(e)},
                status=500
            )

    async def _handle_generic_webhook(self, request: web.Request) -> web.Response:
        "Handle generic webhook without source in URL."
        try:
            payload = await request.json()
            source = payload.get(source, generic)
        except json.JSONDecodeError:
            return web.json_response({error: Invalid JSON}, status=400)
        
        incident = await self.detector.process_webhook(source, payload)
        return web.json_response({
            status: accepted,
            incident_id: incident.id
        })

    async def _health_check(self, request: web.Request) -> web.Response:
        "Health check endpoint."
        return web.json_response({
            status: healthy,
            active_incidents: len(self.detector.get_active_incidents()),
            version: 0.1.0
        })

    async def _list_incidents(self, request: web.Request) -> web.Response:
        "List all active incidents."
        incidents = self.detector.get_active_incidents()
        return web.json_response({
            count: len(incidents),
            incidents: [i.to_dict() for i in incidents]
        })

    async def _get_incident(self, request: web.Request) -> web.Response:
        "Get details of a specific incident."
        incident_id = request.match_info[id]
        incidents = self.detector.get_active_incidents()
        
        for incident in incidents:
            if incident.id == incident_id:
                return web.json_response(incident.to_dict())
        
        return web.json_response({error: Incident not found}, status=404)

    async def _resolve_incident(self, request: web.Request) -> web.Response:
        "Mark an incident as resolved."
        incident_id = request.match_info[id]
        incident = await self.detector.resolve_incident(incident_id)
        
        if incident:
            return web.json_response({
                status: resolved,
                incident: incident.to_dict()
            })
        return web.json_response({error: Incident not found}, status=404)

    async def _get_stats(self, request: web.Request) -> web.Response:
        "Get MTTR statistics."
        stats = await self.detector.storage.get_mttr_stats()
        return web.json_response(stats)

    def run(self, host: str = 0.0.0.0, port: int = 8080):
        "Start the webhook server."
        logger.info(fStarting Incident Copilot server on host:port)
        web.run_app(self.app, host=host, port=port)


def main():
    "Main entry point."
    import yaml
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format=%(asctime)s [%(levelname)s] %(name)s: %(message)s
    )
    
    # Load configuration
    config_path = sys.argv[1] if len(sys.argv) > 1 else config/config.yaml
    
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        logger.warning(fConfig not found at config_path, using defaults)
        config = {}
    
    # Initialize and run
    detector = IncidentDetector(config)
    server = IncidentServer(detector, config)
    
    server_config = config.get(server, {})
    server.run(
        host=server_config.get(host, 0.0.0.0),
        port=server_config.get(port, 8080)
    )


if __name__ == __main__:
    main()
EOF
"""Tests for incident detector."""

import pytest
from datetime import datetime

# Mock the imports for testing without full dependencies
import sys
from unittest.mock import MagicMock, AsyncMock

# Create mock modules
sys.modules['aiohttp'] = MagicMock()
sys.modules['aiohttp.web'] = MagicMock()


class TestWebhookParser:
    """Tests for webhook parsing."""

    def test_parse_prometheus_alert(self):
        """Test parsing Prometheus AlertManager webhook."""
        from src.detector import WebhookParser
        
        payload = {
            "alerts": [{
                "status": "firing",
                "labels": {
                    "alertname": "HighErrorRate",
                    "severity": "critical",
                    "service": "api-gateway"
                },
                "annotations": {
                    "summary": "High error rate detected",
                    "description": "Error rate is 50%"
                },
                "fingerprint": "abc123"
            }]
        }
        
        incident = WebhookParser.parse_prometheus(payload)
        
        assert incident.id == "prom-abc123"
        assert "HighErrorRate" in incident.title
        assert incident.source == "prometheus"
        assert incident.labels["service"] == "api-gateway"

    def test_parse_pagerduty_webhook(self):
        """Test parsing PagerDuty webhook."""
        from src.detector import WebhookParser
        
        payload = {
            "event": {
                "event_type": "incident.triggered",
                "data": {
                    "id": "PT4KHLK",
                    "title": "High CPU Usage",
                    "description": "CPU above 90%",
                    "urgency": "high",
                    "service": {"name": "production-api"}
                }
            }
        }
        
        incident = WebhookParser.parse_pagerduty(payload)
        
        assert incident.id == "pd-PT4KHLK"
        assert incident.title == "High CPU Usage"
        assert incident.source == "pagerduty"

    def test_parse_generic_webhook(self):
        """Test parsing generic webhook."""
        from src.detector import WebhookParser
        
        payload = {
            "id": "custom-001",
            "title": "Custom Alert",
            "description": "Something happened",
            "severity": "medium",
            "labels": {"env": "production"}
        }
        
        incident = WebhookParser.parse_generic(payload)
        
        assert "custom" in incident.id
        assert incident.title == "Custom Alert"
        assert incident.source == "custom"


class TestIncident:
    """Tests for Incident dataclass."""

    def test_incident_mttr_calculation(self):
        """Test MTTR calculation."""
        from src.detector import Incident, IncidentSeverity, IncidentStatus
        
        incident = Incident(
            id="test-001",
            title="Test Incident",
            description="Test",
            severity=IncidentSeverity.HIGH,
            source="test",
            triggered_at=datetime(2024, 1, 15, 10, 0, 0),
            resolved_at=datetime(2024, 1, 15, 10, 45, 30),
        )
        
        assert incident.mttr_seconds == 45 * 60 + 30  # 45 minutes 30 seconds

    def test_incident_mttr_none_when_not_resolved(self):
        """Test MTTR is None when not resolved."""
        from src.detector import Incident, IncidentSeverity
        
        incident = Incident(
            id="test-002",
            title="Test Incident",
            description="Test",
            severity=IncidentSeverity.MEDIUM,
            source="test",
        )
        
        assert incident.mttr_seconds is None

    def test_incident_to_dict(self):
        """Test incident serialization."""
        from src.detector import Incident, IncidentSeverity, IncidentStatus
        
        incident = Incident(
            id="test-003",
            title="Test Incident",
            description="Test description",
            severity=IncidentSeverity.CRITICAL,
            source="prometheus",
            labels={"service": "api"}
        )
        
        data = incident.to_dict()
        
        assert data["id"] == "test-003"
        assert data["severity"] == "critical"
        assert data["labels"]["service"] == "api"


class TestIncidentSeverity:
    """Tests for severity enum."""

    def test_severity_values(self):
        """Test severity enum values."""
        from src.detector import IncidentSeverity
        
        assert IncidentSeverity.CRITICAL.value == "critical"
        assert IncidentSeverity.HIGH.value == "high"
        assert IncidentSeverity.MEDIUM.value == "medium"
        assert IncidentSeverity.LOW.value == "low"
        assert IncidentSeverity.INFO.value == "info"


@pytest.mark.asyncio
async def test_detector_initialization():
    """Test IncidentDetector initialization."""
    from src.detector import IncidentDetector
    
    config = {
        "ai": {"provider": "ollama"},
        "log_sources": [],
        "notifications": {"enabled": False}
    }
    
    detector = IncidentDetector(config)
    
    assert detector.config == config
    assert detector.get_active_incidents() == []

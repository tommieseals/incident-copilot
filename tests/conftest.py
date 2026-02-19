"""Pytest configuration and fixtures."""

import pytest
import sys
from unittest.mock import MagicMock
from datetime import datetime


# Mock aiohttp for testing without network
@pytest.fixture(autouse=True)
def mock_aiohttp():
    """Mock aiohttp module."""
    mock = MagicMock()
    sys.modules['aiohttp'] = mock
    sys.modules['aiohttp.web'] = mock
    yield mock


@pytest.fixture
def sample_incident():
    """Create a sample incident for testing."""
    from src.detector import Incident, IncidentSeverity, IncidentStatus
    
    return Incident(
        id="test-incident-001",
        title="Test High Error Rate",
        description="Error rate spiked to 50%",
        severity=IncidentSeverity.HIGH,
        source="prometheus",
        status=IncidentStatus.TRIGGERED,
        triggered_at=datetime(2024, 1, 15, 10, 30, 0),
        labels={
            "service": "api-gateway",
            "namespace": "production",
            "deployment": "api-gateway"
        }
    )


@pytest.fixture
def sample_logs():
    """Sample log entries for testing."""
    return [
        "[2024-01-15 10:29:55] [api-gateway] [ERROR] Connection timeout to database",
        "[2024-01-15 10:29:56] [api-gateway] [ERROR] Connection pool exhausted",
        "[2024-01-15 10:29:57] [api-gateway] [ERROR] Failed to acquire connection",
        "[2024-01-15 10:29:58] [api-gateway] [WARN] Retrying database connection",
        "[2024-01-15 10:29:59] [api-gateway] [ERROR] Max retries exceeded",
        "[2024-01-15 10:30:00] [api-gateway] [INFO] Health check failed",
    ]


@pytest.fixture
def sample_analysis():
    """Sample analysis result for testing."""
    return {
        "root_cause": "Database connection pool exhaustion",
        "confidence": 85,
        "evidence": [
            "Multiple 'connection pool exhausted' errors",
            "Connection count at maximum",
        ],
        "affected_components": ["api-gateway", "database"],
        "timeline": [
            {"time": "10:29:55", "event": "First timeout error"},
            {"time": "10:30:00", "event": "Health check failed"},
        ],
        "similar_incidents": []
    }


@pytest.fixture
def mock_config():
    """Sample configuration for testing."""
    return {
        "server": {
            "host": "0.0.0.0",
            "port": 8080
        },
        "ai": {
            "provider": "ollama",
            "endpoint": "http://localhost:11434",
            "model": "llama3.2:3b"
        },
        "log_sources": [
            {
                "name": "test-logs",
                "type": "file",
                "paths": ["/tmp/test.log"]
            }
        ],
        "notifications": {
            "enabled": False
        },
        "storage": {
            "backend": "sqlite",
            "path": ":memory:"
        }
    }

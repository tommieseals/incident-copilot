"""Tests for AI analyzer."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestPatternMatcher:
    """Tests for quick pattern matching."""

    def test_match_oom_pattern(self):
        """Test OOM pattern matching."""
        from src.analyzer import PatternMatcher
        
        logs = [
            "[ERROR] Process killed by OOM killer",
            "[ERROR] Out of memory: Cannot allocate memory",
            "[INFO] Starting process",
        ]
        
        result = PatternMatcher.quick_match(logs)
        
        assert result is not None
        assert result["pattern_name"] == "oom_kill"
        assert "memory" in result["root_cause"].lower()

    def test_match_connection_pool_pattern(self):
        """Test connection pool pattern matching."""
        from src.analyzer import PatternMatcher
        
        logs = [
            "[ERROR] Connection pool exhausted",
            "[ERROR] No available connections in pool",
            "[WARN] Connection timeout",
        ]
        
        result = PatternMatcher.quick_match(logs)
        
        assert result is not None
        assert result["pattern_name"] == "connection_pool"

    def test_match_timeout_pattern(self):
        """Test timeout pattern matching."""
        from src.analyzer import PatternMatcher
        
        logs = [
            "[ERROR] Request timed out after 30s",
            "[ERROR] Deadline exceeded for operation",
        ]
        
        result = PatternMatcher.quick_match(logs)
        
        assert result is not None
        assert result["pattern_name"] == "timeout"

    def test_no_match(self):
        """Test no pattern match."""
        from src.analyzer import PatternMatcher
        
        logs = [
            "[INFO] Application started successfully",
            "[INFO] Request processed in 50ms",
        ]
        
        result = PatternMatcher.quick_match(logs)
        
        assert result is None


class TestIncidentAnalyzer:
    """Tests for AI analyzer."""

    def test_prepare_logs_prioritizes_errors(self):
        """Test that error logs are prioritized."""
        from src.analyzer import IncidentAnalyzer
        
        analyzer = IncidentAnalyzer({"provider": "ollama", "max_log_lines": 5})
        
        logs = [
            "[INFO] Normal log 1",
            "[INFO] Normal log 2",
            "[ERROR] Critical error",
            "[INFO] Normal log 3",
            "[WARNING] A warning",
            "[INFO] Normal log 4",
            "[INFO] Normal log 5",
            "[INFO] Normal log 6",
        ]
        
        prepared = analyzer._prepare_logs(logs)
        
        # Error should appear first due to prioritization
        assert "[ERROR]" in prepared
        assert "[WARNING]" in prepared

    def test_extract_confidence(self):
        """Test confidence extraction from text."""
        from src.analyzer import IncidentAnalyzer
        
        analyzer = IncidentAnalyzer({})
        
        assert analyzer._extract_confidence("Confidence: 85%") == 85
        assert analyzer._extract_confidence("I am 90% confident") == 90
        assert analyzer._extract_confidence("No confidence mentioned") == 50


class TestAnalysisResult:
    """Tests for AnalysisResult dataclass."""

    def test_analysis_result_to_dict(self):
        """Test AnalysisResult serialization."""
        from src.analyzer import AnalysisResult
        
        result = AnalysisResult(
            root_cause="Database connection issue",
            confidence=0.85,
            evidence=["Timeout errors", "Connection refused"],
            similar_incidents=[],
            affected_components=["api", "database"],
            timeline=[],
            raw_response="Test response"
        )
        
        data = result.to_dict()
        
        assert data["root_cause"] == "Database connection issue"
        assert data["confidence"] == 0.85
        assert len(data["evidence"]) == 2

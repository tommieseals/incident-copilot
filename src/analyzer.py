"""
AI Incident Analyzer - Root cause analysis using LLMs.

Supports:
- Ollama (local)
- OpenAI
- Anthropic
- Azure OpenAI
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """Result of AI analysis."""
    root_cause: str
    confidence: float
    evidence: list[str]
    similar_incidents: list[dict]
    affected_components: list[str]
    timeline: list[dict]
    raw_response: str

    def to_dict(self) -> dict:
        return {
            "root_cause": self.root_cause,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "similar_incidents": self.similar_incidents,
            "affected_components": self.affected_components,
            "timeline": self.timeline,
        }


class AIProvider:
    """Base class for AI providers."""

    async def complete(self, prompt: str, system: str = "") -> str:
        raise NotImplementedError


class OllamaProvider(AIProvider):
    """Ollama local LLM provider."""

    def __init__(self, config: dict):
        self.endpoint = config.get("endpoint", "http://localhost:11434")
        self.model = config.get("model", "llama3.2:3b")
        self.timeout = config.get("timeout", 120)

    async def complete(self, prompt: str, system: str = "") -> str:
        import aiohttp
        
        url = f"{self.endpoint}/api/generate"
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "num_predict": 2048,
            }
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as resp:
                    if resp.status != 200:
                        error = await resp.text()
                        raise Exception(f"Ollama error: {error}")
                    
                    data = await resp.json()
                    return data.get("response", "")
        
        except ImportError:
            # Fallback to requests if aiohttp not available
            import requests
            
            resp = requests.post(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json().get("response", "")


class OpenAIProvider(AIProvider):
    """OpenAI API provider."""

    def __init__(self, config: dict):
        self.api_key = config.get("api_key") or self._get_env_key()
        self.model = config.get("model", "gpt-4o-mini")
        self.endpoint = config.get("endpoint", "https://api.openai.com/v1")

    def _get_env_key(self) -> str:
        import os
        return os.environ.get("OPENAI_API_KEY", "")

    async def complete(self, prompt: str, system: str = "") -> str:
        import aiohttp
        
        url = f"{self.endpoint}/chat/completions"
        
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 2048,
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    raise Exception(f"OpenAI error: {error}")
                
                data = await resp.json()
                return data["choices"][0]["message"]["content"]


class AnthropicProvider(AIProvider):
    """Anthropic Claude API provider."""

    def __init__(self, config: dict):
        self.api_key = config.get("api_key") or self._get_env_key()
        self.model = config.get("model", "claude-3-haiku-20240307")

    def _get_env_key(self) -> str:
        import os
        return os.environ.get("ANTHROPIC_API_KEY", "")

    async def complete(self, prompt: str, system: str = "") -> str:
        import aiohttp
        
        url = "https://api.anthropic.com/v1/messages"
        
        payload = {
            "model": self.model,
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}],
        }
        
        if system:
            payload["system"] = system
        
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    raise Exception(f"Anthropic error: {error}")
                
                data = await resp.json()
                return data["content"][0]["text"]


class IncidentAnalyzer:
    """AI-powered incident root cause analyzer."""

    PROVIDERS = {
        "ollama": OllamaProvider,
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
    }

    SYSTEM_PROMPT = """You are an expert Site Reliability Engineer (SRE) analyzing production incidents.
Your role is to identify root causes from logs, metrics, and system events.

When analyzing, you should:
1. Look for error patterns and their frequency
2. Identify the timeline of events leading to the incident
3. Find correlations between different log sources
4. Consider recent deployments or configuration changes
5. Identify affected components and their dependencies

Always provide:
- A clear root cause hypothesis with confidence level (0-100%)
- Specific evidence from the logs supporting your analysis
- A timeline of events
- List of affected components

Be direct and technical. Focus on actionable insights."""

    def __init__(self, config: dict):
        """Initialize analyzer with AI provider configuration."""
        provider_name = config.get("provider", "ollama").lower()
        
        if provider_name in self.PROVIDERS:
            self.provider = self.PROVIDERS[provider_name](config)
            logger.info(f"Using AI provider: {provider_name}")
        else:
            logger.warning(f"Unknown provider {provider_name}, defaulting to Ollama")
            self.provider = OllamaProvider(config)
        
        self.max_log_lines = config.get("max_log_lines", 500)

    async def analyze(
        self,
        incident: Any,
        logs: list[str]
    ) -> dict:
        """
        Analyze incident with gathered logs.
        Returns structured analysis result.
        """
        # Prepare log context (truncate if too long)
        log_context = self._prepare_logs(logs)
        
        # Build analysis prompt
        prompt = self._build_prompt(incident, log_context)
        
        try:
            # Get AI analysis
            response = await self.provider.complete(prompt, self.SYSTEM_PROMPT)
            
            # Parse structured response
            result = self._parse_response(response)
            
            logger.info(
                f"Analysis complete: {result['root_cause'][:50]}... "
                f"(confidence: {result['confidence']}%)"
            )
            
            return result
        
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return {
                "root_cause": f"Analysis failed: {str(e)}",
                "confidence": 0,
                "evidence": [],
                "similar_incidents": [],
                "affected_components": [],
                "timeline": [],
                "error": str(e),
            }

    def _prepare_logs(self, logs: list[str]) -> str:
        """Prepare logs for AI consumption."""
        # Prioritize error and warning logs
        error_logs = [l for l in logs if "[ERROR]" in l or "[FATAL]" in l]
        warning_logs = [l for l in logs if "[WARNING]" in l or "[WARN]" in l]
        other_logs = [l for l in logs if l not in error_logs and l not in warning_logs]
        
        # Combine with priority
        prioritized = error_logs[:100] + warning_logs[:100] + other_logs
        
        # Truncate to max lines
        truncated = prioritized[:self.max_log_lines]
        
        if len(logs) > len(truncated):
            truncated.append(f"... ({len(logs) - len(truncated)} more log entries truncated)")
        
        return "\n".join(truncated)

    def _build_prompt(self, incident: Any, log_context: str) -> str:
        """Build the analysis prompt."""
        labels = getattr(incident, "labels", {})
        severity = incident.severity.value if hasattr(incident.severity, "value") else incident.severity
        triggered = incident.triggered_at.isoformat() if hasattr(incident.triggered_at, "isoformat") else incident.triggered_at
        
        incident_info = f"""
## Incident Details
- **ID**: {incident.id}
- **Title**: {incident.title}
- **Description**: {incident.description}
- **Severity**: {severity}
- **Source**: {incident.source}
- **Triggered**: {triggered}
- **Labels**: {json.dumps(labels, indent=2)}
"""

        prompt = f"""Analyze the following production incident and determine the root cause.

{incident_info}

## Collected Logs
```
{log_context}
```

## Required Analysis
Please provide your analysis in the following JSON format:

```json
{{
  "root_cause": "Clear description of the most likely root cause",
  "confidence": 85,
  "evidence": [
    "Specific log line or pattern that supports this conclusion",
    "Another piece of evidence"
  ],
  "affected_components": ["component1", "component2"],
  "timeline": [
    {{"time": "HH:MM:SS", "event": "Description of what happened"}},
    {{"time": "HH:MM:SS", "event": "Next event"}}
  ],
  "similar_incidents": [
    {{"id": "Previous incident ID if known", "similarity": 90}}
  ]
}}
```

Focus on identifying actionable root causes. If you are uncertain, explain what additional information would help.
"""
        return prompt

    def _parse_response(self, response: str) -> dict:
        """Parse AI response into structured format."""
        # Try to extract JSON from response
        json_match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
        
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Try to find any JSON object in the response
        json_pattern = r'\{[^{}]*"root_cause"[^{}]*\}'
        match = re.search(json_pattern, response, re.DOTALL)
        
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        
        # Fallback: extract key information manually
        result = {
            "root_cause": self._extract_section(response, "root cause", response[:500]),
            "confidence": self._extract_confidence(response),
            "evidence": self._extract_list(response, "evidence"),
            "affected_components": self._extract_list(response, "affected"),
            "timeline": [],
            "similar_incidents": [],
            "raw_response": response,
        }
        
        return result

    def _extract_section(self, text: str, section: str, default: str = "") -> str:
        """Extract a section from unstructured text."""
        patterns = [
            rf"{section}[:\s]*([^\n]+)",
            rf"\*\*{section}\*\*[:\s]*([^\n]+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return default

    def _extract_confidence(self, text: str) -> int:
        """Extract confidence percentage from text."""
        patterns = [
            r"confidence[:\s]*(\d+)\s*%",
            r"(\d+)\s*%\s*confiden",
            r"(\d+)%",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return min(100, max(0, int(match.group(1))))
        
        return 50  # Default confidence

    def _extract_list(self, text: str, section: str) -> list[str]:
        """Extract a list from text."""
        # Look for bullet points after section header
        pattern = rf"{section}.*?(?:[-•*]\s*([^\n]+))"
        matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
        
        if matches:
            return [m.strip() for m in matches[:5]]
        
        return []


# Pattern matching for common issues
class PatternMatcher:
    """Quick pattern matching for common incident types."""

    PATTERNS = {
        "oom_kill": {
            "patterns": [r"OOM", r"Out of memory", r"killed process", r"memory limit"],
            "root_cause": "Memory exhaustion - process was OOM killed",
            "component": "memory",
        },
        "connection_pool": {
            "patterns": [r"connection pool", r"pool exhausted", r"no available connections"],
            "root_cause": "Database connection pool exhaustion",
            "component": "database",
        },
        "disk_full": {
            "patterns": [r"No space left", r"disk full", r"ENOSPC"],
            "root_cause": "Disk space exhaustion",
            "component": "storage",
        },
        "timeout": {
            "patterns": [r"timeout", r"timed out", r"deadline exceeded"],
            "root_cause": "Request timeout - service not responding in time",
            "component": "network",
        },
        "crash_loop": {
            "patterns": [r"CrashLoopBackOff", r"restarting", r"exit code [1-9]"],
            "root_cause": "Container crash loop - application failing to start",
            "component": "application",
        },
        "ssl_cert": {
            "patterns": [r"certificate", r"SSL", r"TLS", r"x509"],
            "root_cause": "SSL/TLS certificate issue",
            "component": "security",
        },
        "dns": {
            "patterns": [r"DNS", r"name resolution", r"NXDOMAIN", r"could not resolve"],
            "root_cause": "DNS resolution failure",
            "component": "network",
        },
        "rate_limit": {
            "patterns": [r"rate limit", r"429", r"too many requests", r"throttl"],
            "root_cause": "Rate limiting triggered",
            "component": "api",
        },
    }

    @classmethod
    def quick_match(cls, logs: list[str]) -> Optional[dict]:
        """Quick pattern matching on logs."""
        log_text = "\n".join(logs[:200])  # Check first 200 lines
        
        matches = {}
        for name, pattern_info in cls.PATTERNS.items():
            count = 0
            for pattern in pattern_info["patterns"]:
                count += len(re.findall(pattern, log_text, re.IGNORECASE))
            
            if count > 0:
                matches[name] = {
                    "count": count,
                    **pattern_info
                }
        
        if matches:
            # Return the pattern with most matches
            best_match = max(matches.items(), key=lambda x: x[1]["count"])
            return {
                "pattern_name": best_match[0],
                **best_match[1]
            }
        
        return None


if __name__ == "__main__":
    # Example usage
    import asyncio
    
    async def test():
        config = {
            "provider": "ollama",
            "model": "llama3.2:3b",
            "endpoint": "http://localhost:11434"
        }
        
        analyzer = IncidentAnalyzer(config)
        
        # Mock incident
        class MockIncident:
            id = "test-123"
            title = "High error rate on API"
            description = "500 errors spiked to 50%"
            severity = "high"
            source = "prometheus"
            triggered_at = "2024-01-15T10:30:00Z"
            labels = {"service": "api-gateway"}
        
        logs = [
            "[2024-01-15 10:29:55] [api-gateway] [ERROR] Connection timeout to database",
            "[2024-01-15 10:29:56] [api-gateway] [ERROR] Connection pool exhausted",
            "[2024-01-15 10:29:57] [api-gateway] [ERROR] Failed to acquire connection",
        ]
        
        result = await analyzer.analyze(MockIncident(), logs)
        print(json.dumps(result, indent=2))
    
    asyncio.run(test())

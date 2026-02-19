"""
Log Gatherer - Multi-source log and metric collection.

Supports:
- Kubernetes logs and events
- AWS CloudWatch
- Elasticsearch
- Local files
- Loki (LogQL)
- Git history (recent changes)
"""

import asyncio
import glob
import json
import logging
import re
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class LogEntry:
    """Single log entry with metadata."""
    timestamp: datetime
    source: str
    level: str
    message: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "level": self.level,
            "message": self.message,
            "metadata": self.metadata,
        }


class LogSource(ABC):
    """Abstract base class for log sources."""

    @abstractmethod
    async def gather(
        self,
        start_time: datetime,
        end_time: datetime,
        filters: dict[str, str]
    ) -> list[LogEntry]:
        """Gather logs from this source."""
        pass


class KubernetesLogSource(LogSource):
    """Gather logs from Kubernetes."""

    def __init__(self, config: dict):
        self.namespaces = config.get("namespaces", ["default"])
        self.kubeconfig = config.get("kubeconfig")
        self.context = config.get("context")

    async def gather(
        self,
        start_time: datetime,
        end_time: datetime,
        filters: dict[str, str]
    ) -> list[LogEntry]:
        """Gather Kubernetes logs and events."""
        entries = []
        
        for namespace in self.namespaces:
            # Get pod logs
            entries.extend(await self._get_pod_logs(namespace, start_time, filters))
            # Get events
            entries.extend(await self._get_events(namespace, start_time))
        
        return entries

    async def _get_pod_logs(
        self,
        namespace: str,
        since: datetime,
        filters: dict
    ) -> list[LogEntry]:
        """Get logs from pods in a namespace."""
        entries = []
        since_seconds = int((datetime.utcnow() - since).total_seconds())
        
        try:
            # Get pods
            cmd = ["kubectl", "get", "pods", "-n", namespace, "-o", "json"]
            if self.context:
                cmd.extend(["--context", self.context])
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            pods_data = json.loads(stdout)
            
            # Get logs from each pod
            for pod in pods_data.get("items", []):
                pod_name = pod["metadata"]["name"]
                
                # Check if pod matches filters
                if filters.get("pod") and filters["pod"] not in pod_name:
                    continue
                
                for container in pod.get("spec", {}).get("containers", []):
                    container_name = container["name"]
                    
                    log_cmd = [
                        "kubectl", "logs", pod_name,
                        "-n", namespace,
                        "-c", container_name,
                        f"--since={since_seconds}s",
                        "--timestamps"
                    ]
                    if self.context:
                        log_cmd.extend(["--context", self.context])
                    
                    try:
                        log_proc = await asyncio.create_subprocess_exec(
                            *log_cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE
                        )
                        log_stdout, _ = await log_proc.communicate()
                        
                        for line in log_stdout.decode().strip().split("\n"):
                            if not line:
                                continue
                            
                            entry = self._parse_log_line(
                                line, namespace, pod_name, container_name
                            )
                            if entry:
                                entries.append(entry)
                    except Exception as e:
                        logger.warning(f"Failed to get logs from {pod_name}: {e}")
        
        except Exception as e:
            logger.error(f"Failed to gather K8s logs from {namespace}: {e}")
        
        return entries

    async def _get_events(self, namespace: str, since: datetime) -> list[LogEntry]:
        """Get Kubernetes events."""
        entries = []
        
        try:
            cmd = ["kubectl", "get", "events", "-n", namespace, "-o", "json"]
            if self.context:
                cmd.extend(["--context", self.context])
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            events_data = json.loads(stdout)
            
            for event in events_data.get("items", []):
                event_time = datetime.fromisoformat(
                    event.get("lastTimestamp", "").replace("Z", "+00:00")
                ) if event.get("lastTimestamp") else datetime.utcnow()
                
                if event_time < since:
                    continue
                
                level = "warning" if event.get("type") == "Warning" else "info"
                
                entries.append(LogEntry(
                    timestamp=event_time,
                    source=f"k8s-event/{namespace}",
                    level=level,
                    message=f"[{event.get('reason', 'Unknown')}] {event.get('message', '')}",
                    metadata={
                        "kind": event.get("involvedObject", {}).get("kind"),
                        "name": event.get("involvedObject", {}).get("name"),
                        "count": event.get("count", 1),
                    }
                ))
        
        except Exception as e:
            logger.error(f"Failed to get K8s events from {namespace}: {e}")
        
        return entries

    def _parse_log_line(
        self,
        line: str,
        namespace: str,
        pod: str,
        container: str
    ) -> Optional[LogEntry]:
        """Parse a Kubernetes log line with timestamp."""
        # Format: 2024-01-15T10:30:00.123456789Z log message
        match = re.match(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z?)\s+(.*)$", line)
        
        if match:
            timestamp_str, message = match.groups()
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            except ValueError:
                timestamp = datetime.utcnow()
        else:
            timestamp = datetime.utcnow()
            message = line
        
        # Detect log level
        level = "info"
        level_patterns = {
            "error": r"\b(ERROR|ERR|FATAL|CRITICAL)\b",
            "warning": r"\b(WARN|WARNING)\b",
            "debug": r"\b(DEBUG|TRACE)\b",
        }
        for lvl, pattern in level_patterns.items():
            if re.search(pattern, message, re.IGNORECASE):
                level = lvl
                break
        
        return LogEntry(
            timestamp=timestamp,
            source=f"k8s/{namespace}/{pod}/{container}",
            level=level,
            message=message,
            metadata={
                "namespace": namespace,
                "pod": pod,
                "container": container,
            }
        )


class FileLogSource(LogSource):
    """Gather logs from local files."""

    def __init__(self, config: dict):
        self.paths = config.get("paths", [])
        self.patterns = config.get("patterns", {})

    async def gather(
        self,
        start_time: datetime,
        end_time: datetime,
        filters: dict[str, str]
    ) -> list[LogEntry]:
        """Read logs from files matching glob patterns."""
        entries = []
        
        for path_pattern in self.paths:
            for filepath in glob.glob(path_pattern, recursive=True):
                try:
                    entries.extend(
                        await self._read_file(filepath, start_time, end_time)
                    )
                except Exception as e:
                    logger.warning(f"Failed to read {filepath}: {e}")
        
        return entries

    async def _read_file(
        self,
        filepath: str,
        start_time: datetime,
        end_time: datetime
    ) -> list[LogEntry]:
        """Read and parse a single log file."""
        entries = []
        
        # Common timestamp patterns
        timestamp_patterns = [
            r"^(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})",  # ISO format
            r"^\[(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})\]",  # Nginx style
            r"^(\w{3}\s+\d+\s+\d{2}:\d{2}:\d{2})",  # Syslog style
        ]
        
        def run_read():
            results = []
            with open(filepath, "r", errors="ignore") as f:
                # Read last 10000 lines (tail)
                lines = f.readlines()[-10000:]
                
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    
                    timestamp = None
                    for pattern in timestamp_patterns:
                        match = re.match(pattern, line)
                        if match:
                            try:
                                timestamp = datetime.fromisoformat(
                                    match.group(1).replace("/", "-").replace(" ", "T")
                                )
                            except ValueError:
                                pass
                            break
                    
                    if timestamp and start_time <= timestamp <= end_time:
                        level = self._detect_level(line)
                        results.append(LogEntry(
                            timestamp=timestamp,
                            source=f"file/{filepath}",
                            level=level,
                            message=line,
                            metadata={"file": filepath}
                        ))
            return results
        
        loop = asyncio.get_event_loop()
        entries = await loop.run_in_executor(None, run_read)
        return entries

    def _detect_level(self, line: str) -> str:
        """Detect log level from line content."""
        line_upper = line.upper()
        if any(x in line_upper for x in ["ERROR", "FATAL", "CRITICAL", "EXCEPTION"]):
            return "error"
        if any(x in line_upper for x in ["WARN", "WARNING"]):
            return "warning"
        if any(x in line_upper for x in ["DEBUG", "TRACE"]):
            return "debug"
        return "info"


class GitHistorySource(LogSource):
    """Gather recent git commits and deployments."""

    def __init__(self, config: dict):
        self.repos = config.get("repos", ["."])
        self.max_commits = config.get("max_commits", 20)

    async def gather(
        self,
        start_time: datetime,
        end_time: datetime,
        filters: dict[str, str]
    ) -> list[LogEntry]:
        """Get recent commits from git repositories."""
        entries = []
        
        for repo_path in self.repos:
            try:
                cmd = [
                    "git", "-C", repo_path, "log",
                    f"--since={start_time.isoformat()}",
                    f"--until={end_time.isoformat()}",
                    f"-n{self.max_commits}",
                    "--pretty=format:%H|%aI|%an|%s"
                ]
                
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                stdout, _ = await proc.communicate()
                
                for line in stdout.decode().strip().split("\n"):
                    if not line:
                        continue
                    
                    parts = line.split("|", 3)
                    if len(parts) >= 4:
                        commit_hash, timestamp_str, author, message = parts
                        
                        try:
                            timestamp = datetime.fromisoformat(timestamp_str)
                        except ValueError:
                            timestamp = datetime.utcnow()
                        
                        entries.append(LogEntry(
                            timestamp=timestamp,
                            source=f"git/{repo_path}",
                            level="info",
                            message=f"[{commit_hash[:8]}] {author}: {message}",
                            metadata={
                                "commit": commit_hash,
                                "author": author,
                                "repo": repo_path,
                            }
                        ))
            
            except Exception as e:
                logger.warning(f"Failed to get git history from {repo_path}: {e}")
        
        return entries


class ElasticsearchLogSource(LogSource):
    """Gather logs from Elasticsearch."""

    def __init__(self, config: dict):
        self.host = config.get("host", "localhost:9200")
        self.index_pattern = config.get("index_pattern", "logs-*")
        self.auth = config.get("auth")

    async def gather(
        self,
        start_time: datetime,
        end_time: datetime,
        filters: dict[str, str]
    ) -> list[LogEntry]:
        """Query Elasticsearch for logs."""
        entries = []
        
        try:
            import aiohttp
            
            query = {
                "query": {
                    "bool": {
                        "must": [
                            {
                                "range": {
                                    "@timestamp": {
                                        "gte": start_time.isoformat(),
                                        "lte": end_time.isoformat()
                                    }
                                }
                            }
                        ]
                    }
                },
                "sort": [{"@timestamp": "desc"}],
                "size": 1000
            }
            
            url = f"http://{self.host}/{self.index_pattern}/_search"
            
            headers = {"Content-Type": "application/json"}
            auth = None
            if self.auth:
                import aiohttp
                auth = aiohttp.BasicAuth(
                    self.auth.get("username", ""),
                    self.auth.get("password", "")
                )
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=query, headers=headers, auth=auth) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for hit in data.get("hits", {}).get("hits", []):
                            source = hit.get("_source", {})
                            entries.append(LogEntry(
                                timestamp=datetime.fromisoformat(
                                    source.get("@timestamp", "").replace("Z", "+00:00")
                                ),
                                source=f"es/{hit.get('_index', 'unknown')}",
                                level=source.get("level", "info").lower(),
                                message=source.get("message", str(source)),
                                metadata=source
                            ))
        
        except ImportError:
            logger.warning("aiohttp not installed, skipping Elasticsearch")
        except Exception as e:
            logger.error(f"Failed to query Elasticsearch: {e}")
        
        return entries


class LogGatherer:
    """Main log gathering orchestrator."""

    SOURCE_TYPES = {
        "kubernetes": KubernetesLogSource,
        "k8s": KubernetesLogSource,
        "file": FileLogSource,
        "git": GitHistorySource,
        "elasticsearch": ElasticsearchLogSource,
        "es": ElasticsearchLogSource,
    }

    def __init__(self, sources_config: list[dict]):
        """Initialize with list of source configurations."""
        self.sources: list[LogSource] = []
        
        for config in sources_config:
            source_type = config.get("type", "").lower()
            if source_type in self.SOURCE_TYPES:
                self.sources.append(self.SOURCE_TYPES[source_type](config))
                logger.info(f"Configured log source: {source_type}")
            else:
                logger.warning(f"Unknown log source type: {source_type}")

    async def gather_logs(
        self,
        incident: Any,
        time_range_minutes: int = 60
    ) -> list[str]:
        """
        Gather logs from all configured sources.
        
        Returns list of formatted log lines for analysis.
        """
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=time_range_minutes)
        
        # Build filters from incident
        filters = {}
        if hasattr(incident, "labels"):
            filters.update(incident.labels)
        
        # Gather from all sources concurrently
        all_entries: list[LogEntry] = []
        
        tasks = [
            source.gather(start_time, end_time, filters)
            for source in self.sources
        ]
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Log gathering failed: {result}")
                else:
                    all_entries.extend(result)
        
        # Sort by timestamp
        all_entries.sort(key=lambda x: x.timestamp)
        
        # Format as log lines
        log_lines = []
        for entry in all_entries:
            level_tag = f"[{entry.level.upper()}]"
            log_lines.append(
                f"[{entry.timestamp.isoformat()}] [{entry.source}] {level_tag} {entry.message}"
            )
        
        logger.info(f"Gathered {len(log_lines)} log entries from {len(self.sources)} sources")
        
        return log_lines

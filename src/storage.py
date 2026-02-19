"""
Incident Storage - Persistence and MTTR tracking.

Supports:
- SQLite (default, local)
- PostgreSQL
- File-based JSON
"""

import asyncio
import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)


class IncidentStorage:
    """Store and retrieve incidents with MTTR tracking."""

    def __init__(self, config: dict):
        self.config = config
        self.backend = config.get("backend", "sqlite")
        self.db_path = config.get("path", "incidents.db")
        
        if self.backend == "sqlite":
            self._init_sqlite()
        elif self.backend == "json":
            self._init_json()

    def _init_sqlite(self):
        """Initialize SQLite database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS incidents (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                severity TEXT,
                source TEXT,
                status TEXT,
                triggered_at TEXT,
                acknowledged_at TEXT,
                resolved_at TEXT,
                labels TEXT,
                analysis TEXT,
                suggested_fixes TEXT,
                postmortem TEXT,
                mttr_seconds INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_triggered_at 
            ON incidents(triggered_at)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_status 
            ON incidents(status)
        ''')
        
        conn.commit()
        conn.close()
        
        logger.info(f"Initialized SQLite database at {self.db_path}")

    def _init_json(self):
        """Initialize JSON file storage."""
        if not os.path.exists(self.db_path):
            with open(self.db_path, "w") as f:
                json.dump({"incidents": []}, f)
        logger.info(f"Initialized JSON storage at {self.db_path}")

    async def save_incident(self, incident: Any) -> None:
        """Save a new incident."""
        if self.backend == "sqlite":
            await self._save_sqlite(incident)
        elif self.backend == "json":
            await self._save_json(incident)

    async def _save_sqlite(self, incident: Any) -> None:
        """Save incident to SQLite."""
        def _do_save():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO incidents 
                (id, title, description, severity, source, status, 
                 triggered_at, acknowledged_at, resolved_at, labels,
                 analysis, suggested_fixes, postmortem, mttr_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                incident.id,
                incident.title,
                incident.description,
                incident.severity.value if hasattr(incident.severity, "value") else str(incident.severity),
                incident.source,
                incident.status.value if hasattr(incident.status, "value") else str(incident.status),
                incident.triggered_at.isoformat() if hasattr(incident.triggered_at, "isoformat") else str(incident.triggered_at),
                incident.acknowledged_at.isoformat() if incident.acknowledged_at and hasattr(incident.acknowledged_at, "isoformat") else None,
                incident.resolved_at.isoformat() if incident.resolved_at and hasattr(incident.resolved_at, "isoformat") else None,
                json.dumps(getattr(incident, "labels", {})),
                json.dumps(getattr(incident, "analysis", None)),
                json.dumps(getattr(incident, "suggested_fixes", [])),
                getattr(incident, "postmortem", None),
                getattr(incident, "mttr_seconds", None),
            ))
            
            conn.commit()
            conn.close()
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _do_save)
        logger.debug(f"Saved incident {incident.id}")

    async def _save_json(self, incident: Any) -> None:
        """Save incident to JSON file."""
        def _do_save():
            with open(self.db_path, "r") as f:
                data = json.load(f)
            
            incident_data = {
                "id": incident.id,
                "title": incident.title,
                "description": incident.description,
                "severity": incident.severity.value if hasattr(incident.severity, "value") else str(incident.severity),
                "source": incident.source,
                "status": incident.status.value if hasattr(incident.status, "value") else str(incident.status),
                "triggered_at": incident.triggered_at.isoformat() if hasattr(incident.triggered_at, "isoformat") else str(incident.triggered_at),
                "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else None,
                "mttr_seconds": getattr(incident, "mttr_seconds", None),
            }
            
            # Update or append
            existing_idx = next(
                (i for i, inc in enumerate(data["incidents"]) if inc["id"] == incident.id),
                None
            )
            if existing_idx is not None:
                data["incidents"][existing_idx] = incident_data
            else:
                data["incidents"].append(incident_data)
            
            with open(self.db_path, "w") as f:
                json.dump(data, f, indent=2)
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _do_save)

    async def update_incident(self, incident: Any) -> None:
        """Update an existing incident."""
        await self.save_incident(incident)

    async def get_incident(self, incident_id: str) -> Optional[dict]:
        """Retrieve an incident by ID."""
        if self.backend == "sqlite":
            def _do_get():
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
                row = cursor.fetchone()
                conn.close()
                return dict(row) if row else None
            
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, _do_get)
        
        return None

    async def get_mttr_stats(self, days: int = 30) -> dict:
        """Calculate MTTR statistics."""
        if self.backend == "sqlite":
            return await self._get_mttr_sqlite(days)
        elif self.backend == "json":
            return await self._get_mttr_json(days)
        return {}

    async def _get_mttr_sqlite(self, days: int) -> dict:
        """Get MTTR stats from SQLite."""
        def _do_query():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
            
            # Overall stats
            cursor.execute('''
                SELECT 
                    COUNT(*) as total,
                    AVG(mttr_seconds) as avg_mttr,
                    MIN(mttr_seconds) as min_mttr,
                    MAX(mttr_seconds) as max_mttr,
                    SUM(CASE WHEN status = 'resolved' THEN 1 ELSE 0 END) as resolved,
                    SUM(CASE WHEN status != 'resolved' THEN 1 ELSE 0 END) as active
                FROM incidents 
                WHERE triggered_at > ?
            ''', (cutoff,))
            
            overall = cursor.fetchone()
            
            # Last 24h
            day_cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
            cursor.execute('''
                SELECT AVG(mttr_seconds) as avg_mttr, COUNT(*) as count
                FROM incidents 
                WHERE triggered_at > ? AND status = 'resolved'
            ''', (day_cutoff,))
            day_stats = cursor.fetchone()
            
            # Last 7 days
            week_cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
            cursor.execute('''
                SELECT AVG(mttr_seconds) as avg_mttr, COUNT(*) as count
                FROM incidents 
                WHERE triggered_at > ? AND status = 'resolved'
            ''', (week_cutoff,))
            week_stats = cursor.fetchone()
            
            # By severity
            cursor.execute('''
                SELECT severity, AVG(mttr_seconds) as avg_mttr, COUNT(*) as count
                FROM incidents 
                WHERE triggered_at > ? AND status = 'resolved'
                GROUP BY severity
            ''', (cutoff,))
            severity_stats = cursor.fetchall()
            
            conn.close()
            
            def format_time(seconds):
                if seconds is None:
                    return "N/A"
                minutes = int(seconds // 60)
                secs = int(seconds % 60)
                if minutes >= 60:
                    hours = minutes // 60
                    minutes = minutes % 60
                    return f"{hours}h {minutes}m"
                return f"{minutes}m {secs}s"
            
            return {
                "period_days": days,
                "total_incidents": overall[0] or 0,
                "resolved": overall[4] or 0,
                "active": overall[5] or 0,
                "mttr": {
                    "average": format_time(overall[1]),
                    "average_seconds": overall[1],
                    "min": format_time(overall[2]),
                    "max": format_time(overall[3]),
                },
                "last_24h": {
                    "average": format_time(day_stats[0]),
                    "count": day_stats[1] or 0,
                },
                "last_7d": {
                    "average": format_time(week_stats[0]),
                    "count": week_stats[1] or 0,
                },
                "by_severity": {
                    row[0]: {
                        "average": format_time(row[1]),
                        "count": row[2],
                    }
                    for row in severity_stats
                },
            }
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _do_query)

    async def _get_mttr_json(self, days: int) -> dict:
        """Get MTTR stats from JSON storage."""
        def _do_calc():
            with open(self.db_path, "r") as f:
                data = json.load(f)
            
            cutoff = datetime.utcnow() - timedelta(days=days)
            incidents = data.get("incidents", [])
            
            resolved = [
                i for i in incidents 
                if i.get("status") == "resolved" 
                and i.get("mttr_seconds")
                and datetime.fromisoformat(i["triggered_at"]) > cutoff
            ]
            
            if not resolved:
                return {
                    "period_days": days,
                    "total_incidents": len(incidents),
                    "resolved": 0,
                    "mttr": {"average": "N/A", "average_seconds": None},
                }
            
            avg_mttr = sum(i["mttr_seconds"] for i in resolved) / len(resolved)
            
            return {
                "period_days": days,
                "total_incidents": len(incidents),
                "resolved": len(resolved),
                "mttr": {
                    "average": f"{int(avg_mttr // 60)}m {int(avg_mttr % 60)}s",
                    "average_seconds": avg_mttr,
                },
            }
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _do_calc)


if __name__ == "__main__":
    # Test storage
    import asyncio
    
    async def test():
        storage = IncidentStorage({"backend": "sqlite", "path": "test_incidents.db"})
        stats = await storage.get_mttr_stats()
        print(json.dumps(stats, indent=2))
    
    asyncio.run(test())

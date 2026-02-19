"""
CLI - Command-line interface for Incident Copilot.

Usage:
    python -m src.cli stats       # Show MTTR statistics
    python -m src.cli incidents   # List active incidents
    python -m src.cli analyze     # Manually trigger analysis
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

import yaml

from .storage import IncidentStorage
from .detector import IncidentDetector


def load_config(config_path: str = "config/config.yaml") -> dict:
    """Load configuration from YAML file."""
    try:
        with open(config_path) as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}


def print_box(content: list[str], title: str = None):
    """Print content in a nice box."""
    width = max(len(line) for line in content) + 2
    if title:
        width = max(width, len(title) + 4)
    
    print("┌" + "─" * width + "┐")
    if title:
        print(f"│ {title.center(width - 2)} │")
        print("├" + "─" * width + "┤")
    
    for line in content:
        print(f"│ {line.ljust(width - 2)} │")
    
    print("└" + "─" * width + "┘")


async def cmd_stats(args):
    """Show MTTR statistics."""
    config = load_config(args.config)
    storage = IncidentStorage(config.get("storage", {}))
    
    stats = await storage.get_mttr_stats(days=args.days)
    
    content = [
        f"Last 24h:  {stats['last_24h']['average']}  ({stats['last_24h']['count']} incidents)",
        f"Last 7d:   {stats['last_7d']['average']}  ({stats['last_7d']['count']} incidents)",
        f"Last {args.days}d:  {stats['mttr']['average']}  ({stats['resolved']} resolved)",
        f"",
        f"Total:     {stats['total_incidents']} incidents, {stats['active']} active",
    ]
    
    if stats.get("by_severity"):
        content.append("")
        content.append("By Severity:")
        for sev, data in stats["by_severity"].items():
            content.append(f"  {sev.upper()}: {data['average']} avg ({data['count']})")
    
    print_box(content, "MTTR Dashboard")
    
    if args.json:
        print("\n" + json.dumps(stats, indent=2))


async def cmd_incidents(args):
    """List incidents."""
    config = load_config(args.config)
    storage = IncidentStorage(config.get("storage", {}))
    
    # This would need implementation to list from storage
    print("Active Incidents:")
    print("  (Run server to see active incidents)")


async def cmd_analyze(args):
    """Manually trigger analysis on an incident."""
    config = load_config(args.config)
    
    if args.payload:
        with open(args.payload) as f:
            payload = json.load(f)
    else:
        print("Enter incident JSON (Ctrl+D to finish):")
        payload = json.load(sys.stdin)
    
    detector = IncidentDetector(config)
    incident = await detector.process_webhook(args.source or "manual", payload)
    
    print(f"\nIncident created: {incident.id}")
    print(f"Status: {incident.status.value}")
    
    if args.wait:
        print("\nWaiting for analysis...")
        await asyncio.sleep(30)  # Wait for processing


def main():
    parser = argparse.ArgumentParser(
        description="Incident Copilot CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m src.cli stats              # Show MTTR statistics
    python -m src.cli stats --days 7     # Last 7 days
    python -m src.cli incidents          # List incidents
    python -m src.cli analyze -f inc.json # Analyze incident
        """
    )
    
    parser.add_argument(
        "-c", "--config",
        default="config/config.yaml",
        help="Path to config file"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # stats command
    stats_parser = subparsers.add_parser("stats", help="Show MTTR statistics")
    stats_parser.add_argument("--days", type=int, default=30, help="Number of days")
    stats_parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    # incidents command
    inc_parser = subparsers.add_parser("incidents", help="List incidents")
    inc_parser.add_argument("--status", help="Filter by status")
    inc_parser.add_argument("--limit", type=int, default=10, help="Number to show")
    
    # analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Manually analyze incident")
    analyze_parser.add_argument("-f", "--payload", help="JSON payload file")
    analyze_parser.add_argument("-s", "--source", help="Source name")
    analyze_parser.add_argument("--wait", action="store_true", help="Wait for analysis")
    
    args = parser.parse_args()
    
    if args.command == "stats":
        asyncio.run(cmd_stats(args))
    elif args.command == "incidents":
        asyncio.run(cmd_incidents(args))
    elif args.command == "analyze":
        asyncio.run(cmd_analyze(args))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

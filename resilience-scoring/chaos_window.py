#!/usr/bin/env python3
import json
import subprocess
from datetime import datetime, timezone, timedelta
from typing import Tuple


def parse_timestamp(timestamp: str) -> datetime:
    """Convert Kubernetes timestamp into a timezone-aware datetime."""
    return datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def get_observation_window(
    chaos_kind: str,
    chaos_name: str,
    chaos_namespace: str,
    observation_seconds: int = 300,
) -> Tuple[datetime, datetime]:
    """
    Inspect the chaos object (via kubectl) and return the fault start
    and the observation end (fault_start + observation_seconds).
    """
    result = subprocess.run(
        [
            "kubectl",
            "get",
            chaos_kind,
            chaos_name,
            "-n",
            chaos_namespace,
            "-o",
            "json",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    chaos = json.loads(result.stdout)

    events = chaos["status"]["experiment"]["containerRecords"][0]["events"]

    apply_event = next(event for event in events if event["operation"] == "Apply")

    fault_start = parse_timestamp(apply_event["timestamp"])

    observation_end = fault_start + timedelta(seconds=observation_seconds)

    return fault_start, observation_end

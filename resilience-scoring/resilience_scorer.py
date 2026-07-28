#!/usr/bin/env python3

import argparse
import json
import subprocess
from datetime import datetime, timezone, timedelta


def parse_timestamp(timestamp: str) -> datetime:
    """Convert Kubernetes timestamp into a Python datetime."""

    return datetime.strptime(
        timestamp,
        "%Y-%m-%dT%H:%M:%SZ"
    ).replace(tzinfo=timezone.utc)


def get_observation_window(
    chaos_kind: str,
    chaos_name: str,
    chaos_namespace: str,
    observation_seconds: int = 300,
):
    """
    Returns

        fault_start
        observation_end

    observation_end is simply:

        fault_start + observation_seconds (5m)
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

    apply_event = next(
        event
        for event in events
        if event["operation"] == "Apply"
    )

    fault_start = parse_timestamp(apply_event["timestamp"])

    observation_end = fault_start + timedelta(
        seconds=observation_seconds
    )

    return fault_start, observation_end


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument("--chaos-kind", required=True)
    parser.add_argument("--chaos-name", required=True)
    parser.add_argument(
        "--chaos-namespace",
        default="chaos-mesh",
    )

    parser.add_argument(
        "--observation-window",
        type=int,
        default=300,
        help="Observation window in seconds",
    )

    args = parser.parse_args()

    fault_start, observation_end = get_observation_window(
        chaos_kind=args.chaos_kind,
        chaos_name=args.chaos_name,
        chaos_namespace=args.chaos_namespace,
        observation_seconds=args.observation_window,
    )

    print("\nObservation Window")
    print("----------------------------")
    print(f"Fault start     : {fault_start}")
    print(f"Observation end : {observation_end}")
    print(
        f"Window length   : {(observation_end - fault_start).total_seconds()} seconds"
    )


if __name__ == "__main__":
    main()
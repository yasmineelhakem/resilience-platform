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

def get_pod_lifecycle_mttr(namespace: str, label_selector: str, fault_start: datetime):
    """
    MTTR for pod-kill experiments where app-level metrics don't move.
    Measures: time from fault_start until a Ready replacement pod exists.
    """
    result = subprocess.run(
        ["kubectl", "get", "pods", "-n", namespace,
         "-l", label_selector, "-o", "json"],
        capture_output=True, text=True, check=True
    )
    pods = json.loads(result.stdout)["items"]

    # find pods created AT or AFTER the fault — the replacement(s)
    candidates = []
    for pod in pods:
        created = parse_timestamp(pod["metadata"]["creationTimestamp"])
        if created >= fault_start:
            candidates.append(pod)

    if not candidates:
        raise RuntimeError("No replacement pod found after fault_start — "
                            "check label_selector or that recovery has happened.")

    # take the earliest-created replacement (in case of retries/crashloops)
    replacement = min(candidates, key=lambda p: p["metadata"]["creationTimestamp"])

    ready_condition = next(
        c for c in replacement["status"]["conditions"] if c["type"] == "Ready"
    )
    if ready_condition["status"] != "True":
        raise RuntimeError("Replacement pod exists but is not Ready yet — "
                            "run again once it stabilizes.")

    ready_time = parse_timestamp(ready_condition["lastTransitionTime"])
    mttr_seconds = (ready_time - fault_start).total_seconds()

    return round(mttr_seconds, 1), replacement["metadata"]["name"], ready_time

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

    mttr, pod_name, ready_time = get_pod_lifecycle_mttr(
        namespace="otel-demo",
        label_selector="app.kubernetes.io/component=cart",
        fault_start=fault_start,
    )
    print(f"\nPod-lifecycle MTTR")
    print("----------------------------")
    print(f"Replacement pod : {pod_name}")
    print(f"Ready at        : {ready_time}")
    print(f"MTTR            : {mttr} seconds")


if __name__ == "__main__":
    main()

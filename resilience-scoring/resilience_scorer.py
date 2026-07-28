#!/usr/bin/env python3

import argparse
import json
import subprocess
from datetime import datetime, timezone, timedelta
import requests

PROMETHEUS_URL = "http://localhost:9090"

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

def get_p99_latency_series(service_name: str, start: datetime, end: datetime, step="5s"):
    query = (
        f'histogram_quantile(0.99, sum(rate(traces_span_metrics_duration_milliseconds_bucket'
        f'{{service_name="{service_name}"}}[3m])) by (le))'
    )
    resp = requests.get(f"{PROMETHEUS_URL}/api/v1/query_range", params={
        "query": query,
        "start": start.timestamp(),
        "end": end.timestamp(),
        "step": step,
    })
    resp.raise_for_status()
    result = resp.json()["data"]["result"]
    if not result:
        return []
    return [(float(t), float(v)) for t, v in result[0]["values"]]


def get_baseline_p99(service_name: str, fault_start: datetime, baseline_seconds=300):
    baseline_start = fault_start - timedelta(seconds=baseline_seconds)
    series = get_p99_latency_series(service_name, baseline_start, fault_start, step="15s")
    vals = [v for _, v in series if v is not None]
    return sum(vals) / len(vals) if vals else None


def get_latency_mttr(service_name: str, fault_start: datetime, observation_end: datetime,
                      tolerance=1.2, sustain_seconds=30, step_seconds=5):
    """
    MTTR = time from fault_start until p99 latency drops back to within
    """
    baseline = get_baseline_p99(service_name, fault_start)
    if baseline is None or baseline == 0:
        return None, None

    threshold = baseline * tolerance
    series = get_p99_latency_series(service_name, fault_start, observation_end, step=f"{step_seconds}s")
    if not series:
        return None, baseline

    sustain_samples_needed = sustain_seconds // step_seconds
    consecutive_ok = 0
    for i, (ts, val) in enumerate(series):
        if val is not None and val <= threshold:
            consecutive_ok += 1
            if consecutive_ok >= sustain_samples_needed:
                recovery_ts = series[i - sustain_samples_needed + 1][0]
                return round(recovery_ts - fault_start.timestamp(), 1), round(baseline, 1)
        else:
            consecutive_ok = 0
    return None, round(baseline, 1)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chaos-kind", required=True)
    parser.add_argument("--chaos-name", required=True)
    parser.add_argument("--chaos-namespace", default="chaos-mesh")
    parser.add_argument("--observation-window", type=int, default=300)

    # the service actually being killed (for pod-lifecycle MTTR)
    parser.add_argument("--target-component", required=True,
                         help="Value of app.kubernetes.io/component for the killed pod, e.g. cart or payment")

    # the downstream service to measure latency impact on (for dependency MTTR)
    parser.add_argument("--downstream-service", default=None,
                         help="Service to check for latency degradation, e.g. checkout. Omit to skip.")

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
    print(f"Window length   : {(observation_end - fault_start).total_seconds()} seconds")

    mttr, pod_name, ready_time = get_pod_lifecycle_mttr(
        namespace="otel-demo",
        label_selector=f"app.kubernetes.io/component={args.target_component}",
        fault_start=fault_start,
    )
    print(f"\nPod-lifecycle MTTR ({args.target_component})")
    print("----------------------------")
    print(f"Replacement pod : {pod_name}")
    print(f"Ready at        : {ready_time}")
    print(f"MTTR            : {mttr} seconds")

    if args.downstream_service:
        mttr, baseline = get_latency_mttr(args.downstream_service, fault_start, observation_end)
        print(f"\nLatency-based MTTR for dependency failure ({args.downstream_service})")
        print("----------------------------")
        print(f"Baseline p99    : {baseline} ms")
        print(f"MTTR            : {mttr} seconds")


if __name__ == "__main__":
    main()
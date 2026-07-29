#!/usr/bin/env python3
import json
import math
import subprocess
from datetime import datetime
from typing import Optional, Tuple

from chaos_window import parse_timestamp
from metrics import get_p99_latency_series, get_baseline_p99, get_container_cpu_series, get_container_memory_series


def get_pod_lifecycle_mttr(namespace: str, label_selector: str, fault_start: datetime) -> Tuple[float, str, datetime]:
    """
    Determine MTTR for pod-kill experiments by finding the replacement pod
    created at or after `fault_start` and returning the time until its Ready condition.
    """
    result = subprocess.run(
        ["kubectl", "get", "pods", "-n", namespace, "-l", label_selector, "-o", "json"],
        capture_output=True,
        text=True,
        check=True,
    )
    pods = json.loads(result.stdout)["items"]

    candidates = []
    for pod in pods:
        created = parse_timestamp(pod["metadata"]["creationTimestamp"])
        if created >= fault_start:
            candidates.append(pod)

    if not candidates:
        raise RuntimeError(
            "No replacement pod found after fault_start — check label_selector or that recovery has happened."
        )

    replacement = min(candidates, key=lambda p: p["metadata"]["creationTimestamp"])

    ready_condition = next(c for c in replacement["status"]["conditions"] if c["type"] == "Ready")
    if ready_condition["status"] != "True":
        raise RuntimeError("Replacement pod exists but is not Ready yet — run again once it stabilizes.")

    ready_time = parse_timestamp(ready_condition["lastTransitionTime"])
    mttr_seconds = (ready_time - fault_start).total_seconds()

    return round(mttr_seconds, 1), replacement["metadata"]["name"], ready_time


def get_latency_mttr(service_name: str, fault_start: datetime, observation_end: datetime,
                     tolerance: float = 1.2, sustain_seconds: int = 30, step_seconds: int = 5) -> Tuple[Optional[float], Optional[float]]:
    """
    MTTR based on downstream latency: time from `fault_start` until p99 drops back to within
    `tolerance * baseline` and remains there for `sustain_seconds`.
    Returns (mttr_seconds_or_None, baseline_ms_or_None).
    """
    baseline = get_baseline_p99(service_name, fault_start)
    if baseline is None or baseline == 0:
        return None, None

    threshold = baseline * tolerance
    series = get_p99_latency_series(service_name, fault_start, observation_end, step=f"{step_seconds}s")
    if not series:
        return None, round(baseline, 1)

    sustain_samples_needed = sustain_seconds // step_seconds
    consecutive_ok = 0
    fault_detected = False  # Track if latency spiked above threshold first

    for i, (ts, val) in enumerate(series):
        # Ignore empty or NaN samples
        if val is None or math.isnan(val):
            continue

        # Detect that the latency fault has actually started
        if val > threshold:
            fault_detected = True
            consecutive_ok = 0
            continue

        # Only evaluate recovery if we previously registered the fault spike
        if fault_detected and val <= threshold:
            consecutive_ok += 1
            if consecutive_ok >= sustain_samples_needed:
                recovery_ts = series[i - sustain_samples_needed + 1][0]
                mttr = recovery_ts - fault_start.timestamp()
                return round(max(0.0, mttr), 1), round(baseline, 1)

    return None, round(baseline, 1)

def get_cpu_stress_mttr(
    pod_prefix: str,
    fault_start: datetime,
    observation_end: datetime,
    namespace: str = "otel-demo",
    cpu_surge_threshold: float = 0.5,     # Cores required to confirm stress started
    cpu_recovery_threshold: float = 0.15,  # Cores threshold to confirm recovery
    sustain_seconds: int = 30,
    step_seconds: int = 5
) -> Tuple[Optional[float], Optional[float]]:
    """
    Calculates MTTR for CPU stress chaos by observing CPU usage surge and drop back to normal.
    Returns (mttr_seconds_or_None, peak_cpu_cores_or_None).
    """
    series = get_container_cpu_series(pod_prefix, namespace, fault_start, observation_end, step=f"{step_seconds}s")
    if not series:
        return None, None

    sustain_samples_needed = sustain_seconds // step_seconds
    consecutive_ok = 0
    fault_detected = False
    peak_cpu = 0.0

    for i, (ts, val) in enumerate(series):
        if val > peak_cpu:
            peak_cpu = val

        # Detect that CPU stress injected successfully
        if val >= cpu_surge_threshold:
            fault_detected = True
            consecutive_ok = 0
            continue

        # Evaluate recovery when CPU usage drops back down
        if fault_detected and val <= cpu_recovery_threshold:
            consecutive_ok += 1
            if consecutive_ok >= sustain_samples_needed:
                recovery_ts = series[i - sustain_samples_needed + 1][0]
                mttr = recovery_ts - fault_start.timestamp()
                return round(max(0.0, mttr), 1), round(peak_cpu, 2)

    return None, round(peak_cpu, 2)


def get_memory_stress_mttr(
    pod_prefix: str,
    fault_start: datetime,
    observation_end: datetime,
    namespace: str = "otel-demo",
    memory_surge_mb: float = 1.0,         # MB above local baseline to register fault
    sustain_seconds: int = 30,
    step_seconds: int = 5
) -> Tuple[Optional[float], Optional[float]]:
    """
    Calculates MTTR for Memory stress chaos using RSS memory.
    Dynamically uses the start-of-fault value as baseline.
    Returns (mttr_seconds_or_None, peak_memory_mb_or_None).
    """
    series = get_container_memory_series(pod_prefix, namespace, fault_start, observation_end, step=f"{step_seconds}s")
    if not series or len(series) < 2:
        return None, None

    # Use the first data point (at fault_start) as local baseline
    local_baseline = series[0][1]

    surge_threshold = local_baseline + memory_surge_mb
    recovery_threshold = local_baseline + 0.5  # Allow 0.5 MB tolerance above start baseline

    sustain_samples_needed = sustain_seconds // step_seconds
    consecutive_ok = 0
    fault_detected = False
    peak_mem = 0.0

    for i, (ts, val) in enumerate(series):
        if val > peak_mem:
            peak_mem = val

        # 1. Detect memory stress injection spike
        if val >= surge_threshold:
            fault_detected = True
            consecutive_ok = 0
            continue

        # 2. Evaluate recovery when RSS memory drops back down
        if fault_detected and val <= recovery_threshold:
            consecutive_ok += 1
            if consecutive_ok >= sustain_samples_needed:
                recovery_ts = series[i - sustain_samples_needed + 1][0]
                mttr = recovery_ts - fault_start.timestamp()
                return round(max(0.0, mttr), 1), round(peak_mem, 1)

    return None, round(peak_mem, 1)
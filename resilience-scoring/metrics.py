#!/usr/bin/env python3
import requests
from datetime import datetime, timedelta

PROMETHEUS_URL = "http://localhost:9090"


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

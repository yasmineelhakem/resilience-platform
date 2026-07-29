#!/usr/bin/env python3
import math
import requests
from datetime import datetime, timedelta

PROMETHEUS_URL = "http://localhost:9090"

# Map downstream services to their primary outbound dependency span names
SERVICE_SPAN_MAP = {
    "frontend": "oteldemo.ProductCatalogService/GetProduct",
    "checkout": "oteldemo.PaymentService/Charge",
}


def get_p99_latency_series(service_name: str, start: datetime, end: datetime, step="5s"):
    span_name = SERVICE_SPAN_MAP.get(service_name)

    # Use explicit span_name if mapped; otherwise, fall back to all outbound client calls
    if span_name:
        label_filter = f'service_name="{service_name}", span_name="{span_name}"'
    else:
        label_filter = f'service_name="{service_name}", span_kind="SPAN_KIND_CLIENT"'

    query = (
        f'histogram_quantile(0.99, sum(rate(traces_span_metrics_duration_milliseconds_bucket'
        f'{{{label_filter}}}[2m])) by (le))'
    )

    resp = requests.get(
        f"{PROMETHEUS_URL}/api/v1/query_range",
        params={
            "query": query,
            "start": start.timestamp(),
            "end": end.timestamp(),
            "step": step,
        },
    )
    resp.raise_for_status()
    result = resp.json()["data"]["result"]
    if not result:
        return []

    parsed_series = []
    for t, v in result[0]["values"]:
        val = float(v) if v is not None else None
        # Convert string 'NaN' / float('nan') into None for consistent handling
        if val is not None and math.isnan(val):
            val = None
        parsed_series.append((float(t), val))

    return parsed_series


def get_baseline_p99(service_name: str, fault_start: datetime, baseline_seconds=300, default_fallback=5.0):
    baseline_start = fault_start - timedelta(seconds=baseline_seconds)
    series = get_p99_latency_series(service_name, baseline_start, fault_start, step="15s")
    
    # Filter out None and NaN values
    valid_vals = [v for _, v in series if v is not None and not math.isnan(v)]
    
    # Fallback to default threshold if service was completely idle prior to experiment
    if not valid_vals:
        return default_fallback

    return sum(valid_vals) / len(valid_vals)

def get_container_cpu_series(pod_prefix: str, namespace: str, start: datetime, end: datetime, step="5s"):
    """
    Retrieves container CPU rate (in cores) for pods matching a prefix.
    """
    query = f'sum(rate(container_cpu_usage_seconds_total{{namespace="{namespace}", pod=~"{pod_prefix}-.*", container!=""}}[2m])) or vector(0)'
    
    resp = requests.get(
        f"{PROMETHEUS_URL}/api/v1/query_range",
        params={
            "query": query,
            "start": start.timestamp(),
            "end": end.timestamp(),
            "step": step,
        },
    )
    resp.raise_for_status()
    result = resp.json()["data"]["result"]
    if not result:
        return []

    parsed_series = []
    for t, v in result[0]["values"]:
        val = float(v) if v is not None else 0.0
        if math.isnan(val):
            val = 0.0
        parsed_series.append((float(t), val))

    return parsed_series


def get_container_memory_series(pod_prefix: str, namespace: str, start: datetime, end: datetime, step="5s"):
    """
    Retrieves container memory RSS (in MB) for pods matching a prefix.
    Using RSS prevents cache-flush baseline shifts during memory chaos.
    """
    query = f'sum(container_memory_rss{{namespace="{namespace}", pod=~"{pod_prefix}-.*", container!=""}}) / (1024 * 1024)'
    
    resp = requests.get(
        f"{PROMETHEUS_URL}/api/v1/query_range",
        params={
            "query": query,
            "start": start.timestamp(),
            "end": end.timestamp(),
            "step": step,
        },
    )
    resp.raise_for_status()
    result = resp.json()["data"]["result"]
    if not result:
        return []

    parsed_series = []
    for t, v in result[0]["values"]:
        val = float(v) if v is not None else 0.0
        if math.isnan(val):
            val = 0.0
        parsed_series.append((float(t), val))

    return parsed_series
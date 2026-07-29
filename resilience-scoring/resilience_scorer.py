#!/usr/bin/env python3

import argparse
from datetime import timedelta

from chaos_window import get_observation_window
from mttr import get_pod_lifecycle_mttr, get_latency_mttr


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chaos-kind", required=True)
    parser.add_argument("--chaos-name", required=True)
    parser.add_argument("--chaos-namespace", default="chaos-mesh")
    parser.add_argument("--observation-window", type=int, default=300)

    parser.add_argument(
        "--target-component",
        required=True,
        help="Value of app.kubernetes.io/component for the killed pod, e.g. cart or payment",
    )

    parser.add_argument(
        "--downstream-service",
        default=None,
        help="Service to check for latency degradation, e.g. checkout. Omit to skip.",
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
    print(f"Window length   : {(observation_end - fault_start).total_seconds()} seconds")

    mttr_pod, pod_name, ready_time = get_pod_lifecycle_mttr(
        namespace="otel-demo",
        label_selector=f"app.kubernetes.io/component={args.target_component}",
        fault_start=fault_start,
    )

    print(f"\nPod-lifecycle MTTR ({args.target_component})")
    print("----------------------------")
    print(f"Replacement pod : {pod_name}")
    print(f"Ready at        : {ready_time}")
    print(f"MTTR            : {mttr_pod} seconds")

    if args.downstream_service:
        mttr_latency, baseline = get_latency_mttr(
            args.downstream_service, fault_start, observation_end
        )
        print(f"\nLatency-based MTTR for dependency failure ({args.downstream_service})")
        print("----------------------------")
        print(f"Baseline p99    : {baseline} ms")
        print(f"MTTR            : {mttr_latency} seconds")


if __name__ == "__main__":
    main()
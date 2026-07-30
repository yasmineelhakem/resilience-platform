#!/usr/bin/env python3

import argparse
from datetime import timedelta

from chaos_window import get_observation_window
from mttr import (
    get_pod_lifecycle_mttr,
    get_latency_mttr,
    get_cpu_stress_mttr,
    get_memory_stress_mttr,
)
from metrics import get_request_availability
from scorer import compute_resilience_score, calculate_burn_rate
from exporter import setup_meter, push_resilience_metrics

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chaos-kind", required=True)
    parser.add_argument("--chaos-name", required=True)
    parser.add_argument("--chaos-namespace", default="chaos-mesh")
    parser.add_argument("--observation-window", type=int, default=300)

    parser.add_argument(
        "--target-component",
        default=None,
        help="Value of app.kubernetes.io/component, for pod-lifecycle MTTR.",
    )

    parser.add_argument(
        "--downstream-service",
        default=None,
        help="Service to check for metrics, e.g., frontend.",
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

    mttr_value = None

    # 1. Pod Lifecycle MTTR
    if args.target_component:
        try:
            mttr_value, pod_name, ready_time = get_pod_lifecycle_mttr(
                namespace="otel-demo",
                label_selector=f"app.kubernetes.io/component={args.target_component}",
                fault_start=fault_start,
            )
            print(f"\nPod-lifecycle MTTR ({args.target_component})")
            print("----------------------------")
            print(f"Replacement pod : {pod_name}")
            print(f"Ready at        : {ready_time}")
            print(f"MTTR            : {mttr_value} seconds")
        except RuntimeError as exc:
            print(f"\nPod-lifecycle MTTR skipped: {exc}")

    # 2. Stress Chaos MTTR
    elif args.chaos_kind == "StressChaos" and args.downstream_service:
        print(f"\nStress Chaos MTTR ({args.downstream_service})")
        print("----------------------------")
        if "cpu" in args.chaos_name.lower():
            mttr_value, peak_val = get_cpu_stress_mttr(
                pod_prefix=args.downstream_service,
                fault_start=fault_start,
                observation_end=observation_end,
            )
            print(f"Stress Type     : CPU")
            print(f"Peak CPU Usage  : {peak_val} cores")
            print(f"MTTR            : {mttr_value} seconds")

        elif "memory" in args.chaos_name.lower() or "mem" in args.chaos_name.lower():
            mttr_value, peak_val = get_memory_stress_mttr(
                pod_prefix=args.downstream_service,
                fault_start=fault_start,
                observation_end=observation_end,
            )
            print(f"Stress Type     : Memory")
            print(f"Peak Memory     : {peak_val} MB")
            print(f"MTTR            : {mttr_value} seconds")

    # 3. Latency MTTR
    elif args.downstream_service:
        mttr_value, baseline = get_latency_mttr(
            args.downstream_service, fault_start, observation_end
        )
        print(f"\nLatency-based MTTR ({args.downstream_service})")
        print("----------------------------")
        print(f"Baseline p99    : {baseline} ms")
        print(f"MTTR            : {mttr_value} seconds")

    # Compute Availability, Burn Rate, and Resilience Score 
    service_to_check = args.downstream_service or args.target_component
    if service_to_check:
        avail = get_request_availability(service_to_check, fault_start, observation_end)
        burn = calculate_burn_rate(availability_pct=avail, slo_target=0.99)
        
        score_details = compute_resilience_score(
            availability_pct=avail,
            mttr_seconds=mttr_value,
            burn_rate=burn,
            mttr_ceiling_sec=float(args.observation_window) 
        )

        print(f"\nSRE Reliability & Resilience Score ({service_to_check})")
        print("==========================================")
        print(f"Request Availability : {avail}%  (Score: {score_details['availability_score']}/100)")
        print(f"Burn Rate            : {burn}x    (Score: {score_details['burn_rate_score']}/100)")
        print(f"MTTR Score           : {mttr_value}s (Score: {score_details['mttr_score']}/100)")
        print("------------------------------------------")
        print(f"FINAL RESILIENCE SCORE: {score_details['final_resilience_score']} / 100")
        print("==========================================")


        if service_to_check:
            # Compute availability and burn rate from Prometheus
            avail_pct = get_request_availability(service_to_check, fault_start, observation_end)
            burn_rate = calculate_burn_rate(availability_pct=avail_pct, slo_target=0.99)
            
            # Compute 0-100 scores
            scores = compute_resilience_score(
                availability_pct=avail_pct,
                mttr_seconds=mttr_value,
                burn_rate=burn_rate,
                mttr_ceiling_sec=float(args.observation_window)
            )

            # Setup OpenTelemetry Meter
            provider, meter = setup_meter()

            # Export computed scores to OTel Collector -> Prometheus
            push_resilience_metrics(
                provider=provider,
                meter=meter,
                experiment_name=args.chaos_name,          
                availability=scores["availability_score"], 
                mttr_score=scores["mttr_score"],          
                burn_score=scores["burn_rate_score"],      
                final_score=scores["final_resilience_score"] 
            )


if __name__ == "__main__":
    main()
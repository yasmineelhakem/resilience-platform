from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

def setup_meter():
    resource = Resource.create({
        "service.name": "resilience-scoring-engine",
        "service.namespace": "otel-demo",
    })

    # OTLP HTTP Exporter pointing to internal K8s otel collector ( after port-forwarding )
    exporter = OTLPMetricExporter(
        endpoint="http://localhost:4317",
        insecure=True
    )

    # 1 second export interval for faster CLI flushing
    reader = PeriodicExportingMetricReader(exporter, export_interval_millis=1000)
    provider = MeterProvider(resource=resource, metric_readers=[reader])
    
    return provider, provider.get_meter("resilience_scorer")


def push_resilience_metrics(
    provider,
    meter,
    experiment_name: str,
    availability: float,
    mttr_score: float,
    burn_score: float,
    final_score: float,
):
    """
    Records and flushes resilience scores to OTEL Collector over HTTP OTLP.
    """
    try:
        # Define Gauges
        availability_gauge = meter.create_gauge(
            "resilience_experiment_availability_score",
            description="Availability score (0-100) per chaos experiment",
            unit="1",
        )
        mttr_gauge = meter.create_gauge(
            "resilience_experiment_mttr_score",
            description="MTTR score (0-100) per chaos experiment",
            unit="1",
        )
        burn_gauge = meter.create_gauge(
            "resilience_experiment_burn_rate_score",
            description="Burn rate score (0-100) per chaos experiment",
            unit="1",
        )
        final_gauge = meter.create_gauge(
            "resilience_experiment_final_score",
            description="Final composite resilience score (0-100) per chaos experiment",
            unit="1",
        )

        attrs = {"experiment": experiment_name}

        # Set values
        availability_gauge.set(availability, attrs)
        mttr_gauge.set(mttr_score, attrs)
        burn_gauge.set(burn_score, attrs)
        final_gauge.set(final_score, attrs)

        # force flush and sh to ensure HTTP request completes before script exits
        provider.shutdown()
        print(f"[Exporter] Successfully exported metrics for experiment '{experiment_name}'.")

    except Exception as e:
        print(f"[Exporter Error] Failed to export metrics: {e}")

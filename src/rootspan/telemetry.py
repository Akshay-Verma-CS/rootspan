"""Shared OpenTelemetry setup for RootSpan and the incident lab."""

# pyright: reportMissingTypeStubs=false

from dataclasses import dataclass

from fastapi import FastAPI
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


@dataclass(frozen=True, slots=True)
class TelemetryConfig:
    """Configuration for one process's OTLP exporters."""

    service_name: str
    endpoint: str
    environment: str = "hackathon"
    enabled: bool = True


def configure_telemetry(application: FastAPI, config: TelemetryConfig) -> None:
    """Instrument one FastAPI process and HTTPX calls with OTLP export."""
    if not config.enabled:
        return

    endpoint = config.endpoint.rstrip("/")
    resource = Resource.create(
        {
            SERVICE_NAME: config.service_name,
            "deployment.environment.name": config.environment,
        }
    )
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces"))
    )
    trace.set_tracer_provider(tracer_provider)

    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=f"{endpoint}/v1/metrics"),
        export_interval_millis=5_000,
    )
    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[metric_reader]))

    FastAPIInstrumentor.instrument_app(application, tracer_provider=tracer_provider)
    HTTPXClientInstrumentor().instrument(tracer_provider=tracer_provider)

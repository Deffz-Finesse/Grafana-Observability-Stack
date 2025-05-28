## lib/otel.py


import os
from opentelemetry import trace
from lib.logger import get_logger
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.sqlite3 import SQLite3Instrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SpanExporter,
    SpanExportResult,
)


# Environment configuration
OTEL_SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "")                              # Logical service name (used in Tempo and Grafana)
OTEL_GRPC_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "localhost:4317")     # OTLP gRPC exporter endpoint (e.g., Tempo or collector)

# Initialize logger for OTEL setup
logger = get_logger("Otel Exporter")


# Custom SpanExporter wrapper that can log spans before sending them
class LoggingSpanExporter(SpanExporter):
    def __init__(self, exporter: SpanExporter):
        self.exporter = exporter                            # Wraps another exporter (e.g., OTLP exporter)

    def export(self, spans) -> SpanExportResult:
        return self.exporter.export(spans)                  # Forward spans to real exporter

    def shutdown(self):
        return self.exporter.shutdown()                     # Pass shutdown to real exporter

    def force_flush(self, timeout_millis: int = 30000):
        return self.exporter.force_flush(timeout_millis)    # Pass flush to exporter


# Main setup function — called once during app bootstrap
def setup_otel():
    resource = Resource(attributes={SERVICE_NAME: OTEL_SERVICE_NAME})   # Attach service name to all spans

    trace.set_tracer_provider(TracerProvider(resource=resource))        # Set global provider
    tracer_provider = trace.get_tracer_provider()                       # Retrieve it to register span processors

    tracer = trace.get_tracer("otel-init")                              # Local tracer for setup instrumentation

    with tracer.start_as_current_span("initialize-otel"):               # Span wraps entire setup
        logger.info("Initializing OpenTelemetry tracing")

        try:
            otlp_exporter = OTLPSpanExporter(endpoint=OTEL_GRPC_ENDPOINT, insecure=True)        # OTLP gRPC connection
            logging_exporter = LoggingSpanExporter(otlp_exporter)                               # Optional: wrap with LoggingSpanExporter
            tracer_provider.add_span_processor(BatchSpanProcessor(logging_exporter))            # Batch processor for efficiency
            logger.info("OTLP exporter connected to %s", OTEL_GRPC_ENDPOINT)                    # Confirm connection
        except Exception as e:
            logger.exception("Failed to initialize OTLP exporter: %s", e)                       # Fatal error during setup
            return  # Exit early to avoid crashing app


        # Automatically instrument popular Python libraries
        RedisInstrumentor().instrument()                                # Trace Redis commands (e.g., cache, queue)
        RequestsInstrumentor().instrument()                             # Trace outbound HTTP requests
        LoggingInstrumentor().instrument(set_logging_format=True)       # Inject trace IDs into log lines
        SQLite3Instrumentor().instrument()                              # Trace SQLite queries
        Psycopg2Instrumentor().instrument()                             # Trace PostgreSQL DB queries via psycopg2
        
        logger.info("OpenTelemetry instrumentations initialized")       # Confirm all hooks registered


# Returns a tracer for a given component (shown in Tempo UI as 'instrumentation library')
def get_tracer(name: str = OTEL_SERVICE_NAME) -> trace.Tracer:
    return trace.get_tracer(name)  # Named tracer, typically per-module or per-feature
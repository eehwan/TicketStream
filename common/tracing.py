import logging
import os
from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# aiokafka는 모든 서비스에서 사용하지 않을 수 있으므로 조건부 임포트
try:
    from opentelemetry.instrumentation.aiokafka import AIOKafkaInstrumentor
    _has_aiokafka = True
except ImportError:
    _has_aiokafka = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_telemetry(app: FastAPI) -> None:
    """
    Sets up OpenTelemetry for the FastAPI application.
    This includes a tracer provider, Jaeger exporter, and instrumentation for
    FastAPI, requests, and aiokafka.
    """
    service_name = os.getenv("OTEL_SERVICE_NAME")
    if not service_name:
        logger.warning("OTEL_SERVICE_NAME environment variable not set. Defaulting to 'unknown_service'.")
        service_name = "unknown_service"

    resource = Resource(attributes={
        "service.name": service_name
    })

    # Set up a TracerProvider and JaegerExporter
    provider = TracerProvider(resource=resource)
    jaeger_exporter = JaegerExporter(
        agent_host_name=os.getenv("OTEL_EXPORTER_JAEGER_AGENT_HOST", "localhost"),
        agent_port=int(os.getenv("OTEL_EXPORTER_JAEGER_AGENT_PORT", "6831")),
    )
    provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))
    trace.set_tracer_provider(provider)

    logger.info(f"Telemetry setup for service: {service_name}")
    logger.info(f"Jaeger agent host: {os.getenv('OTEL_EXPORTER_JAEGER_AGENT_HOST')}")
    logger.info(f"Jaeger agent port: {os.getenv('OTEL_EXPORTER_JAEGER_AGENT_PORT')}")


    # Instrument the FastAPI application.
    FastAPIInstrumentor.instrument_app(app)

    # Instrument other libraries
    RequestsInstrumentor().instrument()
    if _has_aiokafka:
        AIOKafkaInstrumentor().instrument()
        logger.info("AIOKafka has been instrumented.")

    logger.info("FastAPI and Requests have been instrumented.")
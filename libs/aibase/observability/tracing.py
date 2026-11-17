from collections.abc import Iterator
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter
from opentelemetry.trace import Span

_TRACER_NAME = "aibase"


def setup_tracing(
    service_name: str, endpoint: str | None = None, exporter: SpanExporter | None = None
) -> TracerProvider:
    """Backend-agnostic: any OTLP/HTTP endpoint works. Pass `exporter` to inject one in tests."""
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    if exporter is None and endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        exporter = OTLPSpanExporter(endpoint=endpoint)
    if exporter is not None:
        provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return provider


def tracer() -> trace.Tracer:
    return trace.get_tracer(_TRACER_NAME)


@contextmanager
def llm_span(
    operation: str, *, provider: str, model: str | None, prompt_version: str | None = None
) -> Iterator[Span]:
    """Span using OTel GenAI semantic conventions (experimental; pin OTEL_SEMCONV_STABILITY_OPT_IN).

    Prompt/completion content is deliberately never attached: it may contain PHI.
    """
    with tracer().start_as_current_span(f"{operation} {model or ''}".strip()) as span:
        span.set_attribute("gen_ai.operation.name", operation)
        span.set_attribute("gen_ai.system", provider)
        if model:
            span.set_attribute("gen_ai.request.model", model)
        if prompt_version:
            span.set_attribute("app.prompt.version", prompt_version)
        yield span


def record_usage(span: Span, input_tokens: int, output_tokens: int) -> None:
    span.set_attribute("gen_ai.usage.input_tokens", input_tokens)
    span.set_attribute("gen_ai.usage.output_tokens", output_tokens)

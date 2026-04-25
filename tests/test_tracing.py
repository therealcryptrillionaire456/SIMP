"""
Tests for Distributed Tracing — T27
====================================
"""

import os
import pytest
from simp.organs.quantumarb.tracing import (
    QuantumArbTracer,
    Span,
    TraceContext,
    reset_tracer,
    trace,
)


class TestTraceContext:
    def setup(self):
        import os, sys
        sys.path.insert(0, ".")
        os.environ["TRACE"] = "1"
        from simp.organs.quantumarb.tracing import reset_tracer
        reset_tracer()
    """Tests for TraceContext class."""

    def test_trace_id_length(self):
        """Test that trace IDs are 32 hex characters."""
        ctx = TraceContext(trace_id="a" * 32, span_id="b" * 16)
        assert len(ctx.trace_id) == 32

    def test_span_id_length(self):
        """Test that span IDs are 16 hex characters."""
        ctx = TraceContext(trace_id="a" * 32, span_id="b" * 16)
        assert len(ctx.span_id) == 16

    def test_header_injection(self):
        """Test W3C TraceContext header format."""
        ctx = TraceContext(
            trace_id="abc123" * 5 + "abcd",
            span_id="span12345678",
            parent_span_id=None,
        )
        headers = ctx.to_headers()
        assert "traceparent" in headers
        assert headers["traceparent"].startswith("00-")
        assert "tracestate" in headers

    def test_header_extraction(self):
        """Test extracting trace context from headers."""
        # W3C traceparent: 00-{trace-id}-{parent-id}-{trace-flags}
        # parent-id is parts[3] = 00f067aa0ba902b7, trace-flags = 01
        headers = {
            "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
            "tracestate": "sampled=1",
        }
        ctx = TraceContext.from_headers(headers)
        assert ctx is not None
        assert ctx.trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
        assert ctx.span_id == "00f067aa0ba902b7"
        assert ctx.parent_span_id == "00f067aa0ba902b7"  # W3C parent-id from parts[3]
        assert ctx.sampled is True

    def test_header_extraction_with_parent(self):
        """Test header extraction with a valid parent-id (a real span-id)."""
        headers = {
            # W3C traceparent: 00-{trace-id}-{parent-id}-{trace-flags}
            # parent-id = 00f067aa0ba902b7 (16 hex chars), trace-flags = 01
            "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
        }
        ctx = TraceContext.from_headers(headers)
        assert ctx is not None
        assert ctx.trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
        assert ctx.span_id == "00f067aa0ba902b7"  # span-id of the span that created this
        assert ctx.parent_span_id == "00f067aa0ba902b7"
        assert ctx.sampled is True

    def test_header_extraction_invalid(self):
        """Test that invalid headers return None."""
        headers = {"traceparent": "invalid"}
        ctx = TraceContext.from_headers(headers)
        assert ctx is None

    def test_sampled_flag(self):
        """Test sampled flag in tracestate."""
        headers = {"traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01", "tracestate": "sampled=0"}
        ctx = TraceContext.from_headers(headers)
        assert ctx is not None
        assert ctx.sampled is False


class TestSpan:
    def setup(self):
        import os, sys
        sys.path.insert(0, ".")
        os.environ["TRACE"] = "1"
        from simp.organs.quantumarb.tracing import reset_tracer
        reset_tracer()
    """Tests for Span class."""

    def test_duration_ms_calculation(self):
        """Test span duration calculation."""
        import time
        span = Span(
            trace_id="a" * 32,
            span_id="b" * 16,
            parent_span_id=None,
            name="test_span",
            start_time=time.time() - 1.0,
            end_time=time.time(),
        )
        assert span.duration_ms() >= 990  # At least 990ms
        assert span.duration_ms() <= 1100  # At most 1100ms

    def test_duration_ms_in_progress(self):
        """Test duration calculation for in-progress span."""
        span = Span(
            trace_id="a" * 32,
            span_id="b" * 16,
            parent_span_id=None,
            name="test_span",
        )
        assert span.duration_ms() >= 0  # Should be non-negative


class TestQuantumArbTracer:
    def setup(self):
        import os, sys
        sys.path.insert(0, ".")
        os.environ["TRACE"] = "1"
        from simp.organs.quantumarb.tracing import reset_tracer, QuantumArbTracer
        reset_tracer()
        self.tracer = QuantumArbTracer()
    """Tests for QuantumArbTracer class."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Reset tracer before each test."""
        reset_tracer()
        os.environ["TRACE"] = "1"
        yield
        reset_tracer()

    @pytest.fixture
    def tracer_fixture(self):
        """Get tracer instance (named tracer_fixture to avoid shadowing self.tracer)."""
        return QuantumArbTracer.get_instance()

    def test_singleton(self):
        """Test that tracer is a singleton."""
        tracer1 = QuantumArbTracer.get_instance()
        tracer2 = QuantumArbTracer.get_instance()
        assert tracer1 is tracer2

    def test_span_creation(self):
        """Test creating a span."""
        tracer = self.tracer
        ctx = tracer.start_span("test_operation")
        assert ctx.trace_id is not None
        assert ctx.span_id is not None
        assert len(ctx.trace_id) == 32
        assert len(ctx.span_id) == 16

    def test_span_end(self):
        """Test ending a span."""
        tracer = self.tracer
        ctx = tracer.start_span("test_operation")
        tracer.end_span(ctx, "OK")
        # Span should be flushed
        assert len(tracer._spans) >= 1

    def test_span_with_attributes(self):
        """Test span with attributes."""
        tracer = self.tracer
        ctx = tracer.start_span("test_operation", attributes={"key": "value"})
        assert ctx is not None
        tracer.end_span(ctx)

    def test_nested_spans(self):
        """Test nested span creation."""
        tracer = self.tracer
        parent_ctx = tracer.start_span("parent")
        child_ctx = tracer.start_span("child", parent=parent_ctx)
        assert child_ctx.parent_span_id == parent_ctx.span_id
        tracer.end_span(child_ctx)
        tracer.end_span(parent_ctx)

    def test_add_event(self):
        """Test adding event to span."""
        tracer = self.tracer
        ctx = tracer.start_span("test_operation")
        tracer.add_event(ctx, "custom_event", {"detail": "test"})
        tracer.end_span(ctx)
        assert len(tracer._spans) >= 1

    def test_set_attribute(self):
        """Test setting attribute on span."""
        tracer = self.tracer
        ctx = tracer.start_span("test_operation")
        tracer.set_attribute(ctx, "custom_attr", "custom_value")
        tracer.end_span(ctx)
        assert len(tracer._spans) >= 1

    def test_auto_flush_at_limit(self, tmp_path):
        """Test auto-flush when reaching span limit."""
        # Create tracer with low limit for testing
        tracer = QuantumArbTracer()
        tracer._MAX_SPANS = 5
        QuantumArbTracer._instance = tracer
        
        # Create 5 spans to trigger flush
        for i in range(5):
            ctx = tracer.start_span(f"span_{i}")
            tracer.end_span(ctx)
        
        # Should have flushed
        assert len(tracer._spans) == 0

    def test_inject_extract_headers(self):
        """Test header injection and extraction roundtrip."""
        tracer = self.tracer_fixture
        original_ctx = tracer.start_span("test")
        headers = tracer.inject_headers(original_ctx)
        extracted_ctx = tracer.extract_headers(headers)
        assert extracted_ctx is not None
        assert extracted_ctx.trace_id == original_ctx.trace_id
        assert extracted_ctx.span_id == original_ctx.span_id


class TestTraceDecorator:
    def setup(self):
        import os, sys
        sys.path.insert(0, ".")
        os.environ["TRACE"] = "1"
        from simp.organs.quantumarb.tracing import reset_tracer
        reset_tracer()
    """Tests for @trace decorator."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Reset tracer before each test."""
        reset_tracer()
        os.environ["TRACE"] = "1"
        yield
        reset_tracer()

    def test_decorator_success(self):
        """Test decorator with successful function."""
        @trace("test_function")
        def test_func():
            return "success"
        
        result = test_func()
        assert result == "success"

    def test_decorator_with_args(self):
        """Test decorator passes through arguments."""
        @trace("add_function")
        def add(a, b):
            return a + b
        
        result = add(1, 2)
        assert result == 3

    def test_decorator_exception(self):
        """Test decorator records exceptions."""
        @trace("failing_function")
        def failing_func():
            raise ValueError("test error")
        
        with pytest.raises(ValueError):
            failing_func()

    def test_decorator_disabled(self):
        """Test decorator does nothing when disabled."""
        os.environ["TRACE"] = "0"
        reset_tracer()
        
        @trace("disabled_trace")
        def disabled_func():
            return "result"
        
        result = disabled_func()
        assert result == "result"


class TestResetTracer:
    """Tests for reset_tracer function."""

    def test_reset_clears_instance(self):
        """Test that reset clears the singleton."""
        tracer1 = QuantumArbTracer.get_instance()
        reset_tracer()
        tracer2 = QuantumArbTracer.get_instance()
        assert tracer1 is not tracer2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

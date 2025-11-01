from __future__ import annotations

from feaststore.serving.metrics import Metrics


def test_metrics_render_counts():
    m = Metrics()
    m.observe_request(n_entities=3, latency_ms=4.0)
    m.observe_request(n_entities=2, latency_ms=40.0)
    text = m.render()
    assert "feaststore_requests_total 2" in text
    assert "feaststore_entities_total 5" in text
    assert "feaststore_request_latency_ms_count 2" in text


def test_histogram_buckets_are_cumulative():
    m = Metrics()
    m.observe_request(n_entities=1, latency_ms=3.0)  # falls in le=5 bucket
    text = m.render()
    # everything at or above the 5ms bucket boundary should include the sample
    assert 'feaststore_request_latency_ms_bucket{le="5"} 1' in text
    assert 'feaststore_request_latency_ms_bucket{le="1"} 0' in text
    assert 'feaststore_request_latency_ms_bucket{le="+Inf"} 1' in text

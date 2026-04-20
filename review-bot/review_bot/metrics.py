from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

review_runs_total = Counter(
    "review_runs_total",
    "Total review runs by status and trigger",
    ["status", "trigger"],
)

findings_published_total = Counter(
    "findings_published_total",
    "Total findings published by severity and rule family",
    ["severity", "rule_family"],
)

findings_suppressed_total = Counter(
    "findings_suppressed_total",
    "Total findings suppressed by reason",
    ["reason"],
)

findings_resolved_total = Counter(
    "findings_resolved_total",
    "Total findings resolved by rule_no",
    ["rule_no"],
)

detect_phase_duration_seconds = Histogram(
    "detect_phase_duration_seconds",
    "Detect phase wall-clock time",
    buckets=(5, 15, 30, 60, 120, 300),
)

publish_phase_duration_seconds = Histogram(
    "publish_phase_duration_seconds",
    "Publish phase wall-clock time",
    buckets=(2, 5, 15, 30, 60),
)

llm_call_duration_seconds = Histogram(
    "llm_call_duration_seconds",
    "LLM provider API call duration",
    ["provider"],
    buckets=(1, 5, 10, 20, 40, 60),
)

engine_call_duration_seconds = Histogram(
    "engine_call_duration_seconds",
    "review-engine API call duration",
    buckets=(0.1, 0.5, 1, 3, 10, 30),
)

redis_queue_depth = Gauge(
    "redis_queue_depth",
    "Current RQ queue depth",
    ["queue"],
)

dead_letter_count_total = Gauge(
    "dead_letter_count_total",
    "Total unprocessed dead-letter records",
)

circuit_breaker_state = Gauge(
    "circuit_breaker_state",
    "Circuit breaker state: 0=closed 1=open 2=half_open",
    ["component"],
)

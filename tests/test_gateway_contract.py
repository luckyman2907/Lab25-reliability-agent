from reliability_lab.cache import ResponseCache
from reliability_lab.circuit_breaker import CircuitBreaker
from reliability_lab.gateway import ReliabilityGateway
from reliability_lab.providers import FakeLLMProvider


def test_gateway_returns_response_with_route_reason() -> None:
    provider = FakeLLMProvider("primary", fail_rate=0.0, base_latency_ms=1, cost_per_1k_tokens=0.001)
    breaker = CircuitBreaker("primary", failure_threshold=2, reset_timeout_seconds=1)
    gateway = ReliabilityGateway([provider], {"primary": breaker}, ResponseCache(60, 0.5))
    result = gateway.complete("hello world")
    assert result.text
    assert result.route.startswith("primary:") or result.route.startswith("fallback:") or result.route == "static_fallback"


def test_fallback_chain_and_circuit_open() -> None:
    from reliability_lab.circuit_breaker import CircuitState
    
    primary = FakeLLMProvider("primary", fail_rate=1.0, base_latency_ms=1, cost_per_1k_tokens=0.001)
    backup = FakeLLMProvider("backup", fail_rate=0.0, base_latency_ms=1, cost_per_1k_tokens=0.001)
    
    cb_primary = CircuitBreaker("primary", failure_threshold=2, reset_timeout_seconds=1)
    cb_backup = CircuitBreaker("backup", failure_threshold=2, reset_timeout_seconds=1)
    
    gateway = ReliabilityGateway(
        [primary, backup], 
        {"primary": cb_primary, "backup": cb_backup}, 
        None
    )
    
    # 1st call: primary fails, backup succeeds
    res1 = gateway.complete("hello")
    assert res1.route == "fallback:backup"
    assert cb_primary.failure_count == 1
    
    # 2nd call: primary fails, backup succeeds, primary circuit opens
    res2 = gateway.complete("hello")
    assert res2.route == "fallback:backup"
    assert cb_primary.failure_count == 2
    assert cb_primary.state == CircuitState.OPEN
    
    # 3rd call: primary circuit is OPEN, fails fast, backup succeeds
    res3 = gateway.complete("hello")
    assert res3.route == "fallback:backup"

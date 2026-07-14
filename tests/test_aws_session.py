"""Cross-account STS AssumeRole + graceful in-account fallback tests."""

import pytest

import src.agents.adapters.aws_session as aws_session
from src.agents.adapters.aws_session import SessionResult, assume_role_session
from src.agents.ai.circuit_breaker import CircuitBreaker, State


CREDS = {"AccessKeyId": "AKIA_TEST", "SecretAccessKey": "secret", "SessionToken": "token"}
ROLE = "arn:aws:iam::222222222222:role/deploy"


class FakeSTS:
    """A stand-in STS client recording assume_role calls (no moto)."""

    def __init__(self, *, creds=None, error=None):
        self._creds = creds
        self._error = error
        self.calls: list[dict] = []

    def assume_role(self, **kwargs):
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return {"Credentials": self._creds}


def test_assume_role_builds_session_from_temp_credentials(monkeypatch):
    fake = FakeSTS(creds=CREDS)
    monkeypatch.setattr(aws_session, "_sts_client", lambda region: fake)

    result = assume_role_session(ROLE, region="us-east-1", breaker=CircuitBreaker())

    assert result.assumed is True and result.fell_back is False
    assert fake.calls[0]["RoleArn"] == ROLE
    assert fake.calls[0]["RoleSessionName"] == "platform-agent"
    frozen = result.session.get_credentials().get_frozen_credentials()
    assert frozen.access_key == "AKIA_TEST"
    assert frozen.token == "token"


def test_falls_back_to_in_account_on_assume_failure(monkeypatch):
    fake = FakeSTS(error=RuntimeError("AccessDenied"))
    monkeypatch.setattr(aws_session, "_sts_client", lambda region: fake)
    sentinel = object()
    monkeypatch.setattr(aws_session, "_in_account_session", lambda region: sentinel)

    result = assume_role_session(ROLE, region="us-east-1", breaker=CircuitBreaker())

    assert result.fell_back is True and result.assumed is False
    assert result.session is sentinel
    assert result.role_arn == ROLE  # still records the attempted role for the trace


def test_fallback_disabled_reraises(monkeypatch):
    fake = FakeSTS(error=RuntimeError("AccessDenied"))
    monkeypatch.setattr(aws_session, "_sts_client", lambda region: fake)

    with pytest.raises(RuntimeError):
        assume_role_session(ROLE, fallback=False, breaker=CircuitBreaker())


def test_empty_role_arn_uses_in_account_without_calling_sts(monkeypatch):
    called: list[int] = []
    monkeypatch.setattr(aws_session, "_sts_client", lambda region: called.append(1))
    sentinel = object()
    monkeypatch.setattr(aws_session, "_in_account_session", lambda region: sentinel)

    result = assume_role_session("", region="us-east-1")

    assert result.session is sentinel
    assert result.assumed is False and result.fell_back is False
    assert called == []  # no cross-account requested → STS never touched


def test_external_id_is_threaded_to_assume_role(monkeypatch):
    fake = FakeSTS(creds=CREDS)
    monkeypatch.setattr(aws_session, "_sts_client", lambda region: fake)

    assume_role_session(ROLE, external_id="confused-deputy-guard", breaker=CircuitBreaker())

    assert fake.calls[0]["ExternalId"] == "confused-deputy-guard"


def test_repeated_failures_open_circuit_and_fast_fail(monkeypatch):
    fake = FakeSTS(error=RuntimeError("boom"))
    monkeypatch.setattr(aws_session, "_sts_client", lambda region: fake)
    sentinel = object()
    monkeypatch.setattr(aws_session, "_in_account_session", lambda region: sentinel)
    breaker = CircuitBreaker(failure_threshold=2)

    for _ in range(2):
        assume_role_session(ROLE, breaker=breaker)
    assert breaker.state is State.OPEN

    # Circuit is OPEN: the next call must NOT invoke STS, yet still degrade.
    calls_before = len(fake.calls)
    result = assume_role_session(ROLE, breaker=breaker)

    assert result.fell_back is True
    assert result.session is sentinel
    assert len(fake.calls) == calls_before  # STS not called while open


def test_assume_role_arn_from_env(monkeypatch):
    monkeypatch.delenv("AWS_ASSUME_ROLE_ARN", raising=False)
    assert aws_session.assume_role_arn_from_env() == ""
    monkeypatch.setenv("AWS_ASSUME_ROLE_ARN", ROLE)
    assert aws_session.assume_role_arn_from_env() == ROLE


def test_runtime_client_honors_assume_role_env(monkeypatch):
    """The AgentCore runtime adapter's _client sources a cross-account session."""
    import src.agents.adapters.runtime.aws as aws_mod

    captured: dict = {}

    class FakeSession:
        def client(self, service, region_name=None):
            captured["service"] = service
            captured["region"] = region_name
            return "FAKE_CLIENT"

    def fake_assume(role_arn, *, region=None, **_kwargs):
        captured["role_arn"] = role_arn
        return SessionResult(FakeSession(), role_arn, assumed=bool(role_arn), fell_back=False)

    monkeypatch.setattr(aws_mod, "assume_role_session", fake_assume)
    monkeypatch.setenv("AWS_ASSUME_ROLE_ARN", ROLE)

    client = aws_mod._client("us-east-1")

    assert client == "FAKE_CLIENT"
    assert captured["role_arn"] == ROLE
    assert captured["service"] == aws_mod._SERVICE
    assert captured["region"] == "us-east-1"


def test_runtime_client_in_account_when_env_unset(monkeypatch):
    """Env unset → empty role threaded → behaves as a plain in-account client."""
    import src.agents.adapters.runtime.aws as aws_mod

    captured: dict = {}

    class FakeSession:
        def client(self, service, region_name=None):
            return "IN_ACCOUNT_CLIENT"

    def fake_assume(role_arn, *, region=None, **_kwargs):
        captured["role_arn"] = role_arn
        return SessionResult(FakeSession(), role_arn, assumed=False, fell_back=False)

    monkeypatch.setattr(aws_mod, "assume_role_session", fake_assume)
    monkeypatch.delenv("AWS_ASSUME_ROLE_ARN", raising=False)

    client = aws_mod._client("us-east-1")

    assert client == "IN_ACCOUNT_CLIENT"
    assert captured["role_arn"] == ""  # no cross-account requested

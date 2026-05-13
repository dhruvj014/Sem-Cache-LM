from __future__ import annotations

import pytest

from shared.config.settings import Settings


def test_redis_mode_inherit_uses_explicit_host() -> None:
    s = Settings(redis_mode="inherit", redis_host="custom", redis_ssl=True)
    assert s.redis_host == "custom"
    assert s.redis_ssl is True


def test_redis_mode_local_overrides_tls_off() -> None:
    s = Settings(
        redis_mode="local",
        redis_local_host="mycache",
        redis_local_port=6380,
        redis_local_password="x",
        redis_host="ignored",
        redis_ssl=True,
    )
    assert s.redis_host == "mycache"
    assert s.redis_port == 6380
    assert s.redis_password == "x"
    assert s.redis_ssl is False


def test_redis_mode_local_default_hostname() -> None:
    s = Settings(redis_mode="local", redis_local_host="")
    assert s.redis_host == "redis"


def test_redis_mode_aws_requires_host() -> None:
    with pytest.raises(ValueError, match="REDIS_AWS_HOST"):
        Settings(redis_mode="aws")


def test_redis_mode_aws_applies_tls_defaults() -> None:
    s = Settings(
        redis_mode="aws",
        redis_aws_host="x.cache.amazonaws.com",
        redis_aws_password="secret",
        redis_aws_ssl=True,
    )
    assert s.redis_host == "x.cache.amazonaws.com"
    assert s.redis_port == 6379
    assert s.redis_password == "secret"
    assert s.redis_ssl is True


def test_redis_mode_normalized_case_insensitive() -> None:
    s = Settings(redis_mode="LOCAL", redis_local_host="redis")
    assert s.redis_ssl is False


def test_redis_mode_invalid() -> None:
    with pytest.raises(ValueError, match="REDIS_MODE"):
        Settings(redis_mode="cloud")

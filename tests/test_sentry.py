"""Tests for the Sentry traces sampler."""

import pytest

from pv_site_api.main import traces_sampler


def _ctx(path, method="GET", name="generic", parent=None):
    return {
        "asgi_scope": {"type": "http", "path": path, "method": method},
        "transaction_context": {"name": name},
        "parent_sampled": parent,
    }


@pytest.fixture(autouse=True)
def _not_local(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")


@pytest.mark.parametrize("path", ["/", "/api_status", "/docs", "/swagger", "/favicon.ico"])
def test_noise_is_never_traced(path):
    assert traces_sampler(_ctx(path)) == 0.0


def test_options_is_never_traced():
    assert traces_sampler(_ctx("/sites", method="OPTIONS")) == 0.0


def test_api_routes_use_default_rate():
    assert traces_sampler(_ctx("/sites/abc/pv_actual", method="POST")) == 0.05


def test_errors_are_always_traced():
    assert traces_sampler(_ctx("/sites", name="/error")) == 1.0

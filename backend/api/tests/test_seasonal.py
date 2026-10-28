"""Tests for GET /intel/seasonal."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app)


def test_seasonal_returns_unavailable_when_parquet_missing(tmp_path, monkeypatch):
    import backend.api.routers.intelligence as intel_mod
    monkeypatch.setattr(intel_mod, "_SEASONAL_PARQUET", tmp_path / "nonexistent.parquet")
    resp = client.get("/intel/seasonal?commodity=Tomato&state=Karnataka")
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is False
    assert "reason" in data


def test_seasonal_missing_parquet_has_no_weeks(tmp_path, monkeypatch):
    import backend.api.routers.intelligence as intel_mod
    monkeypatch.setattr(intel_mod, "_SEASONAL_PARQUET", tmp_path / "nonexistent.parquet")
    resp = client.get("/intel/seasonal?commodity=Onion&state=Maharashtra")
    assert resp.json()["weeks"] == []

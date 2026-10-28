"""Tests for GET /geo/districts."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app)


def test_districts_known_state_returns_list():
    resp = client.get("/geo/districts?state=Tamil Nadu")
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "Tamil Nadu"
    assert data["count"] > 0
    first = data["districts"][0]
    assert "district" in first
    assert "lat" in first
    assert "lon" in first


def test_districts_sorted_alphabetically():
    resp = client.get("/geo/districts?state=Tamil Nadu")
    assert resp.status_code == 200
    names = [d["district"] for d in resp.json()["districts"]]
    assert names == sorted(names)


def test_districts_unknown_state_returns_404():
    resp = client.get("/geo/districts?state=Atlantis")
    assert resp.status_code == 404

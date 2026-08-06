"""
Basic tests for the Student Portal app.
Run from the backend/ directory: pytest ../tests/test_app.py
Or from repo root:               PYTHONPATH=backend pytest tests/
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
from app import app as flask_app, db


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    flask_app.config["WTF_CSRF_ENABLED"] = False

    with flask_app.test_client() as client:
        with flask_app.app_context():
            db.create_all()
        yield client


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "healthy"


def test_metrics_endpoint(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert b"app_up" in resp.data


def test_login_page_loads(client):
    resp = client.get("/login")
    assert resp.status_code == 200


def test_register_and_login_flow(client):
    resp = client.post(
        "/register",
        data={"name": "Test User", "email": "test@example.com", "password": "pass1234"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    resp = client.post(
        "/login",
        data={"email": "test@example.com", "password": "pass1234"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Dashboard" in resp.data or b"dashboard" in resp.data.lower()


def test_dashboard_requires_login(client):
    resp = client.get("/dashboard", follow_redirects=True)
    assert resp.status_code == 200
    # Redirected to login page
    assert b"Login" in resp.data or b"login" in resp.data.lower()


def test_duplicate_registration_rejected(client):
    client.post(
        "/register",
        data={"name": "A", "email": "dup@example.com", "password": "pass1234"},
    )
    resp = client.post(
        "/register",
        data={"name": "B", "email": "dup@example.com", "password": "pass1234"},
        follow_redirects=True,
    )
    assert b"already exists" in resp.data

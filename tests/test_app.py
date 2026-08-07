"""
Basic tests for the Student Portal app.
Works in two different layouts:
  - Local dev:  repo/tests/test_app.py, repo/backend/app.py
  - Inside the Docker image: /app/tests/test_app.py, /app/app.py
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_CANDIDATE_DIRS = [
    os.path.join(_HERE, "..", "backend"),  # local dev layout
    "/app",                                 # baked into the Docker image
    os.path.join(_HERE, ".."),              # fallback
]
for _dir in _CANDIDATE_DIRS:
    if os.path.exists(os.path.join(_dir, "app.py")):
        sys.path.insert(0, _dir)
        break

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

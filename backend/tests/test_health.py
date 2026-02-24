"""
Test básico: health check (sin BD).
Ejecutar desde backend/: pytest tests/ -v
"""
import os
import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///tmp/test.db")


@pytest.fixture
def client():
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.get_json() == {"status": "ok"}

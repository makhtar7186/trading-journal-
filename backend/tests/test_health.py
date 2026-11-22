import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_health_ok():
    response = APIClient().get("/api/v1/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


@pytest.mark.django_db
def test_protected_by_default():
    # Le schéma est protégé par la permission par défaut IsAuthenticated.
    response = APIClient().get("/api/v1/schema/")
    assert response.status_code in (401, 403)

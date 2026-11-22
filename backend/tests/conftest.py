import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.strategies.models import Strategy

PASSWORD = "S3cure-pass-for-tests!"


@pytest.fixture(autouse=True)
def _clear_cache():
    # Le throttling du login utilise le cache : on l'isole entre les tests.
    cache.clear()


@pytest.fixture(autouse=True)
def _isolated_storage(settings, tmp_path):
    """Les tests n'écrivent jamais dans le vrai dossier storage/."""
    settings.STORAGE_BACKEND = "local"
    settings.STORAGE_LOCAL_ROOT = str(tmp_path / "storage")


@pytest.fixture
def storage_dir(settings):
    from pathlib import Path

    return Path(settings.STORAGE_LOCAL_ROOT)


@pytest.fixture
def user_a(db):
    return User.objects.create_user(username="alice", password=PASSWORD)


@pytest.fixture
def user_b(db):
    return User.objects.create_user(username="bob", password=PASSWORD)


@pytest.fixture
def client_a(user_a):
    client = APIClient()
    client.force_authenticate(user_a)
    return client


@pytest.fixture
def client_b(user_b):
    client = APIClient()
    client.force_authenticate(user_b)
    return client


@pytest.fixture
def strategy_a(user_a):
    return Strategy.objects.create(user=user_a, name="Breakout")


@pytest.fixture
def strategy_b(user_b):
    return Strategy.objects.create(user=user_b, name="Reversal")


def trade_payload(**overrides):
    payload = {
        "name": "EURUSD London open",
        "trade_date": "2026-11-10T09:30:00Z",
        "market_type": "FOREX",
        "asset": "eurusd",
        "direction": "BUY",
    }
    payload.update(overrides)
    return payload

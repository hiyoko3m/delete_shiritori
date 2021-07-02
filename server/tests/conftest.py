import pytest
from fastapi.testclient import TestClient

from delete_shiritori import main
from delete_shiritori.config import Settings


@pytest.fixture(scope="session")
def settings():
    return Settings()


@pytest.fixture(scope="class")
def client():
    client = TestClient(main.app)

    return client

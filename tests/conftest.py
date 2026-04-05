"""
Configuración compartida para todos los tests.
Carga el .env de test y crea el cliente HTTP de la API.
"""
import os
import pytest
from fastapi.testclient import TestClient

# Aseguramos que haya una API_KEY antes de importar la app
os.environ.setdefault("API_KEY", "test-key-local-12345")

from api_server import app

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def auth_headers():
    return {"X-API-Key": os.environ["API_KEY"]}

# Wallet de prueba pública (Vitalik, sin fondos propios, solo para tests de formato)
TEST_WALLET = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
TEST_NETWORK = "Base Sepolia"
# Wallet inválida para tests negativos
INVALID_WALLET = "0xinvalida"

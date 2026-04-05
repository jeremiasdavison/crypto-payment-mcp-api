"""
Tests de transacciones reales en testnet.
Todos son @pytest.mark.integration — requieren ETH de faucet en la wallet.

Para correrlos:
    pytest tests/test_testnet.py -v -m integration

Antes de correr: conseguí ETH en https://faucet.coinbase.com (Base Sepolia)
"""
import pytest


@pytest.mark.integration
def test_balance_testnet_estructura(client, auth_headers):
    r = client.get("/testnet/balance", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "address" in data
    assert "balance" in data
    assert "has_gas" in data
    assert data["token"] == "ETH"


@pytest.mark.integration
def test_balance_testnet_sin_fondos(client, auth_headers):
    """La wallet puede estar en 0, pero el endpoint debe responder correctamente."""
    r = client.get("/testnet/balance", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    # Si no tiene gas, has_gas debe ser False
    if data["balance"] == 0.0:
        assert data["has_gas"] is False


@pytest.mark.integration
def test_enviar_tx_sin_fondos_retorna_error(client, auth_headers):
    """Si no hay ETH en la wallet, debe retornar error claro (no crashear)."""
    r = client.post("/testnet/send", json={
        "to": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
        "amount": 0.001,
        "network": "Base Sepolia (testnet)",
    }, headers=auth_headers)
    # Con fondos → 200, sin fondos → 400 con mensaje claro
    assert r.status_code in (200, 400)
    if r.status_code == 400:
        assert "insuficiente" in r.json()["detail"].lower() or "error" in r.json()


@pytest.mark.integration
def test_tx_hash_invalido_retorna_pendiente(client, auth_headers):
    """Un hash que no existe en la red retorna 'pendiente' (no confirmado aún)."""
    fake_hash = "0x" + "ab" * 32
    r = client.get(f"/testnet/tx/{fake_hash}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "pendiente"


@pytest.mark.integration
def test_enviar_a_direccion_invalida(client, auth_headers):
    r = client.post("/testnet/send", json={
        "to": "0xinvalida",
        "amount": 0.001,
        "network": "Base Sepolia (testnet)",
    }, headers=auth_headers)
    assert r.status_code == 400
    assert "inválida" in r.json()["detail"]

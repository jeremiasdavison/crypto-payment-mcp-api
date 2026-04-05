"""
Tests de wallet: creación y consulta de balance.
"""
import pytest
from web3 import Web3


def test_crear_wallet_estructura(client, auth_headers):
    r = client.post("/wallet/create", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "address" in data
    assert "private_key" in data
    assert "advertencia" in data


def test_crear_wallet_direccion_valida(client, auth_headers):
    r = client.post("/wallet/create", headers=auth_headers)
    address = r.json()["address"]
    assert Web3.is_address(address), f"Dirección inválida: {address}"


def test_crear_wallet_siempre_diferente(client, auth_headers):
    """Cada wallet generada debe ser única."""
    w1 = client.post("/wallet/create", headers=auth_headers).json()["address"]
    w2 = client.post("/wallet/create", headers=auth_headers).json()["address"]
    assert w1 != w2


def test_balance_wallet_invalida(client, auth_headers):
    r = client.get("/balance?address=0xinvalida", headers=auth_headers)
    assert r.status_code == 400
    assert "inválida" in r.json()["detail"]


def test_balance_red_desconocida(client, auth_headers):
    r = client.get(
        "/balance?address=0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045&network=RedInventada",
        headers=auth_headers,
    )
    assert r.status_code == 400


def test_listar_redes(client, auth_headers):
    r = client.get("/networks", headers=auth_headers)
    assert r.status_code == 200
    redes = r.json()["networks"]
    assert len(redes) >= 3
    assert "Base Sepolia (testnet)" in redes


@pytest.mark.integration
def test_balance_onchain_real(client, auth_headers):
    """Consulta real a Base Sepolia — requiere conexión."""
    r = client.get(
        "/balance?address=0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045&network=Base Sepolia (testnet)",
        headers=auth_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert "balance" in data
    assert data["token"] == "ETH"

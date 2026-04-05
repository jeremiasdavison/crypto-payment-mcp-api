"""
Tests del flujo de pagos: preparar y enviar transacciones.
"""
import pytest


def test_preparar_pago_valido(client, auth_headers):
    r = client.post("/payment/prepare", json={
        "destination": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
        "amount": 10.0,
        "token": "USDC",
    }, headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["amount"] == 10.0
    assert data["token"] == "USDC"
    assert data["status"] == "pendiente_aprobacion"


def test_preparar_pago_ens(client, auth_headers):
    """ENS conocido se resuelve a dirección."""
    r = client.post("/payment/prepare", json={
        "destination": "juan.eth",
        "amount": 5.0,
        "token": "USDT",
    }, headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["to_original"] == "juan.eth"
    assert data["to"] != "juan.eth"  # fue resuelto


def test_preparar_pago_monto_cero_rechazado(client, auth_headers):
    r = client.post("/payment/prepare", json={
        "destination": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
        "amount": 0,
        "token": "USDC",
    }, headers=auth_headers)
    assert r.status_code == 422  # Pydantic rechaza amount=0


def test_enviar_pago_dry_run(client, auth_headers):
    r = client.post("/payment/send", json={
        "destination": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
        "amount": 50.0,
        "token": "USDC",
    }, headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "dry_run"
    assert data["tx_hash"] is None
    assert "50.0" in data["message"]
    assert "USDC" in data["message"]


def test_token_uppercase_normalizado(client, auth_headers):
    """El token debe normalizarse a mayúsculas."""
    r = client.post("/payment/prepare", json={
        "destination": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
        "amount": 1.0,
        "token": "usdc",
    }, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["token"] == "USDC"

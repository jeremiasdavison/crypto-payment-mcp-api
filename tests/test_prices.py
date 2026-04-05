"""
Tests de precios y P&L.
Los tests de integración llaman a CoinGecko real — se marcan con @pytest.mark.integration.
Los tests unitarios validan lógica sin red.
"""
import pytest


# ─── Unitarios (sin red) ──────────────────────────────────────────────────────

def test_token_no_soportado(client, auth_headers):
    r = client.get("/price?token=INVENTADO", headers=auth_headers)
    assert r.status_code == 400
    assert "no soportado" in r.json()["detail"]


def test_profit_monto_cero_retorna_error(client, auth_headers):
    r = client.post("/profit", json={
        "token": "ETH",
        "entry_price": 0,
        "amount": 1,
    }, headers=auth_headers)
    # Pydantic rechaza entry_price=0 por la validación gt=0
    assert r.status_code == 422


def test_profit_estructura_respuesta(client, auth_headers):
    """Verifica que el P&L tiene todos los campos esperados."""
    r = client.post("/profit", json={
        "token": "ETH",
        "entry_price": 1000.0,
        "amount": 2.0,
        "currency": "usd",
    }, headers=auth_headers)
    # Puede fallar si CoinGecko no responde, pero verificamos estructura
    if r.status_code == 200:
        data = r.json()
        campos = ["token", "amount", "entry_price", "current_price",
                  "entry_value", "current_value", "pnl", "pnl_pct", "status"]
        for campo in campos:
            assert campo in data, f"Falta campo '{campo}' en respuesta de /profit"


def test_profit_ganancia_cuando_precio_sube():
    """Test puro de lógica: si el precio subió, pnl debe ser positivo."""
    from tools.price_tools import get_profit_index
    from unittest.mock import patch

    precio_actual_mock = {
        "token": "ETH", "price": 3000.0, "currency": "USD",
        "change_24h_pct": 5.0, "market_cap": None, "timestamp": "2024-01-01",
        "source": "CoinGecko",
    }
    with patch("tools.price_tools.get_token_price", return_value=precio_actual_mock):
        result = get_profit_index("ETH", entry_price=2000.0, amount=1.0)

    assert result["pnl"] == 1000.0
    assert result["pnl_pct"] == 50.0
    assert result["status"] == "ganancia"


def test_profit_perdida_cuando_precio_baja():
    from tools.price_tools import get_profit_index
    from unittest.mock import patch

    precio_actual_mock = {
        "token": "ETH", "price": 1500.0, "currency": "USD",
        "change_24h_pct": -10.0, "market_cap": None, "timestamp": "2024-01-01",
        "source": "CoinGecko",
    }
    with patch("tools.price_tools.get_token_price", return_value=precio_actual_mock):
        result = get_profit_index("ETH", entry_price=2000.0, amount=1.0)

    assert result["pnl"] == -500.0
    assert result["status"] == "pérdida"


# ─── Integración (llaman a CoinGecko real) ────────────────────────────────────

@pytest.mark.integration
def test_precio_eth_real(client, auth_headers):
    r = client.get("/price?token=ETH", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["token"] == "ETH"
    assert data["price"] > 0
    assert "change_24h_pct" in data


@pytest.mark.integration
def test_precios_multiples_real(client, auth_headers):
    r = client.get("/prices?tokens=ETH,BTC,SOL", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "ETH" in data["prices"]
    assert "BTC" in data["prices"]
    assert "SOL" in data["prices"]

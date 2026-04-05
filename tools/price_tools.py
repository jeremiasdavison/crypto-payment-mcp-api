"""
Herramientas de precios y rendimiento usando CoinGecko (free API, sin key).
"""
import requests
from datetime import datetime, timezone

COINGECKO_API = "https://api.coingecko.com/api/v3"

# Mapeo símbolo → CoinGecko ID
COIN_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "MATIC": "matic-network",
    "POL": "matic-network",
    "USDC": "usd-coin",
    "USDT": "tether",
    "BNB": "binancecoin",
    "SOL": "solana",
    "ARB": "arbitrum",
    "OP": "optimism",
    "LINK": "chainlink",
    "UNI": "uniswap",
    "AAVE": "aave",
}


def _coin_id(token: str) -> str | None:
    return COIN_IDS.get(token.upper())


def get_token_price(token: str, vs_currency: str = "usd") -> dict:
    """
    Retorna el precio actual de un token y su variación en 24h.
    Tokens soportados: BTC, ETH, MATIC, USDC, USDT, BNB, SOL, ARB, OP, LINK, UNI, AAVE
    """
    coin_id = _coin_id(token)
    if not coin_id:
        return {"error": f"Token '{token}' no soportado. Tokens disponibles: {list(COIN_IDS.keys())}"}

    try:
        resp = requests.get(
            f"{COINGECKO_API}/simple/price",
            params={
                "ids": coin_id,
                "vs_currencies": vs_currency.lower(),
                "include_24hr_change": "true",
                "include_market_cap": "true",
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json().get(coin_id, {})

        vs = vs_currency.lower()
        price = data.get(vs)
        change_24h = data.get(f"{vs}_24h_change")
        market_cap = data.get(f"{vs}_market_cap")

        if price is None:
            return {"error": "No se obtuvo precio de CoinGecko"}

        return {
            "token": token.upper(),
            "price": round(price, 6),
            "currency": vs.upper(),
            "change_24h_pct": round(change_24h, 2) if change_24h else None,
            "market_cap": market_cap,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "CoinGecko",
        }
    except requests.RequestException as e:
        return {"error": f"Error al consultar CoinGecko: {e}"}


def get_profit_index(
    token: str,
    entry_price: float,
    amount: float,
    vs_currency: str = "usd",
) -> dict:
    """
    Calcula el rendimiento (P&L) de una posición cripto.
    - entry_price: precio de compra en vs_currency
    - amount: cantidad de tokens comprados
    - Retorna: valor actual, ganancia/pérdida en USD y en %, ROI
    """
    if entry_price <= 0 or amount <= 0:
        return {"error": "entry_price y amount deben ser positivos"}

    price_data = get_token_price(token, vs_currency)
    if "error" in price_data:
        return price_data

    current_price = price_data["price"]
    entry_value = entry_price * amount
    current_value = current_price * amount
    pnl_abs = current_value - entry_value
    pnl_pct = ((current_price - entry_price) / entry_price) * 100

    return {
        "token": token.upper(),
        "amount": amount,
        "entry_price": entry_price,
        "current_price": current_price,
        "currency": vs_currency.upper(),
        "entry_value": round(entry_value, 4),
        "current_value": round(current_value, 4),
        "pnl": round(pnl_abs, 4),
        "pnl_pct": round(pnl_pct, 2),
        "status": "ganancia" if pnl_abs >= 0 else "pérdida",
        "change_24h_pct": price_data.get("change_24h_pct"),
        "timestamp": price_data["timestamp"],
    }


def get_multi_price(tokens: list[str], vs_currency: str = "usd") -> dict:
    """Retorna precios actuales de múltiples tokens en una sola llamada."""
    validos = {t.upper(): _coin_id(t) for t in tokens if _coin_id(t)}
    if not validos:
        return {"error": "Ningún token reconocido"}

    ids_str = ",".join(validos.values())
    try:
        resp = requests.get(
            f"{COINGECKO_API}/simple/price",
            params={
                "ids": ids_str,
                "vs_currencies": vs_currency.lower(),
                "include_24hr_change": "true",
            },
            timeout=10,
        )
        resp.raise_for_status()
        raw = resp.json()

        resultados = {}
        for symbol, coin_id in validos.items():
            data = raw.get(coin_id, {})
            vs = vs_currency.lower()
            resultados[symbol] = {
                "price": round(data.get(vs, 0), 6),
                "change_24h_pct": round(data.get(f"{vs}_24h_change", 0), 2),
            }

        return {
            "prices": resultados,
            "currency": vs_currency.upper(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "CoinGecko",
        }
    except requests.RequestException as e:
        return {"error": f"Error al consultar CoinGecko: {e}"}

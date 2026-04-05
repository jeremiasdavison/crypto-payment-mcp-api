"""
Crypto Payments — API REST para GPT Actions (ChatGPT)
======================================================
Corre el server:
    uvicorn api_server:app --reload --port 8000

Para exponer públicamente (necesario para ChatGPT):
    ngrok http 8000
    → copiá la URL https://xxxx.ngrok-free.app

En ChatGPT:
    1. Crear GPT → Configure → Add Action
    2. Import from URL: https://xxxx.ngrok-free.app/openapi.json
    3. Authentication: API Key → Header → X-API-Key → pegar tu clave de wallet.env
    4. Listo

Generar una API key nueva:
    python -c "import secrets; print(secrets.token_urlsafe(32))"
"""
import os
import secrets
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Security, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, Field

load_dotenv("wallet.env")

# ─── AUTH ─────────────────────────────────────────────────────────────────────

API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise RuntimeError("Falta API_KEY en wallet.env. Generá una con: python -c \"import secrets; print(secrets.token_urlsafe(32))\"")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(key: str = Security(api_key_header)):
    if not key or not secrets.compare_digest(key, API_KEY):
        raise HTTPException(status_code=401, detail="API key inválida o ausente")
    return key

from tools.tx_tools import get_testnet_balance, send_native_token, get_tx_status, scan_all_balances

from tools.wallet_tools import (
    consultar_balance_onchain,
    consultar_balance_todas_las_redes,
    crear_nueva_wallet,
    REDES,
)
from tools.payment_tools import preparar_transaccion, ejecutar_pago
from tools.price_tools import get_token_price, get_profit_index, get_multi_price

app = FastAPI(
    title="Crypto Payments API",
    description=(
        "API para operaciones cripto en redes EVM. "
        "Consulta balances on-chain, precios de tokens, cálculo de P&L "
        "y simulación de pagos en Base Sepolia, Polygon y Amoy Testnet. "
        "Requiere header `X-API-Key` en todos los endpoints."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://chat.openai.com", "https://chatgpt.com"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ─── BALANCES ────────────────────────────────────────────────────────────────

@app.get(
    "/balance",
    summary="Balance de una wallet",
    description="Consulta el balance nativo (ETH o MATIC) de una dirección en la red indicada.",
    tags=["Balances"],
)
def balance(
    address: str = Query(..., description="Dirección Ethereum (0x...)"),
    network: str = Query("Base Sepolia (testnet)", description="Red EVM a consultar"),
    _: str = Depends(verify_api_key),
):
    result = consultar_balance_onchain(address, network)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get(
    "/balance/all",
    summary="Balance en todas las redes",
    description="Consulta el balance nativo de una dirección en Base Sepolia, Polygon Mainnet y Amoy Testnet.",
    tags=["Balances"],
)
def balance_all(
    address: str = Query(..., description="Dirección Ethereum (0x...)"),
    _: str = Depends(verify_api_key),
):
    result = consultar_balance_todas_las_redes(address)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get(
    "/networks",
    summary="Redes disponibles",
    description="Lista todas las redes EVM soportadas.",
    tags=["Balances"],
)
def networks(_: str = Depends(verify_api_key)):
    return {"networks": list(REDES.keys())}


# ─── PRECIOS Y P&L ───────────────────────────────────────────────────────────

@app.get(
    "/price",
    summary="Precio actual de un token",
    description="Retorna el precio actual y la variación en 24h. Tokens: BTC, ETH, MATIC, USDC, USDT, BNB, SOL, ARB, OP, LINK, UNI, AAVE.",
    tags=["Precios"],
)
def price(
    token: str = Query(..., description="Símbolo del token. Ej: ETH, BTC, SOL"),
    currency: str = Query("usd", description="Moneda de referencia: usd, eur, ars"),
    _: str = Depends(verify_api_key),
):
    result = get_token_price(token, currency)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get(
    "/prices",
    summary="Precios de múltiples tokens",
    description="Retorna precios actuales de varios tokens en una sola llamada. Ej: tokens=ETH,BTC,SOL",
    tags=["Precios"],
)
def prices(
    tokens: str = Query(..., description="Lista separada por comas. Ej: ETH,BTC,MATIC"),
    currency: str = Query("usd", description="Moneda de referencia: usd, eur, ars"),
    _: str = Depends(verify_api_key),
):
    token_list = [t.strip() for t in tokens.split(",") if t.strip()]
    result = get_multi_price(token_list, currency)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


class ProfitRequest(BaseModel):
    token: str = Field(..., description="Símbolo del token. Ej: ETH, BTC, SOL")
    entry_price: float = Field(..., description="Precio de compra en la moneda de referencia", gt=0)
    amount: float = Field(..., description="Cantidad de tokens en la posición", gt=0)
    currency: str = Field("usd", description="Moneda de referencia: usd, eur")


@app.post(
    "/profit",
    summary="Calcular P&L de una posición",
    description="Calcula ganancia o pérdida comparando el precio de entrada con el precio actual.",
    tags=["Precios"],
)
def profit(body: ProfitRequest, _: str = Depends(verify_api_key)):
    result = get_profit_index(body.token, body.entry_price, body.amount, body.currency)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ─── PAGOS ───────────────────────────────────────────────────────────────────

class PaymentRequest(BaseModel):
    destination: str = Field(..., description="Dirección destino (0x...) o nombre ENS (.eth)")
    amount: float = Field(..., description="Monto a enviar", gt=0)
    token: str = Field("USDC", description="Token a enviar: USDC, ETH, USDT")


@app.post(
    "/payment/prepare",
    summary="Preparar una transacción",
    description="Arma los detalles de la tx (destino, monto, gas estimado) sin ejecutarla.",
    tags=["Pagos"],
)
def payment_prepare(body: PaymentRequest, _: str = Depends(verify_api_key)):
    result = preparar_transaccion(body.destination, body.amount, body.token)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post(
    "/payment/send",
    summary="Enviar un pago (simulación)",
    description=(
        "Prepara y ejecuta un pago cripto. "
        "Actualmente corre en modo dry-run (sin transacción real). "
        "La integración con ZeroDev para transacciones reales viene en la próxima versión."
    ),
    tags=["Pagos"],
)
def payment_send(body: PaymentRequest, _: str = Depends(verify_api_key)):
    user_op = preparar_transaccion(body.destination, body.amount, body.token)
    if "error" in user_op:
        raise HTTPException(status_code=400, detail=user_op["error"])
    result = ejecutar_pago(user_op, dry_run=True)
    return result


# ─── WALLET ──────────────────────────────────────────────────────────────────

@app.post(
    "/wallet/create",
    summary="Crear nueva wallet",
    description=(
        "Genera una nueva wallet EVM (Ethereum, Polygon, Base, etc.). "
        "Retorna dirección pública y clave privada. "
        "IMPORTANTE: guardá la private key en un lugar seguro, nunca la compartas."
    ),
    tags=["Wallet"],
)
def wallet_create(_: str = Depends(verify_api_key)):
    return crear_nueva_wallet()


# ─── TRANSACCIONES REALES (testnet) ──────────────────────────────────────────

class SendTxRequest(BaseModel):
    to: str = Field(..., description="Dirección destino (0x...)")
    amount: float = Field(..., description="Monto en ETH o MATIC", gt=0)
    network: str = Field("Base Sepolia (testnet)", description="Red testnet a usar")


@app.get(
    "/testnet/scan",
    summary="Escanear saldos en todas las redes",
    description=(
        "Consulta el balance de cada wallet testnet en su red correspondiente. "
        "Retorna un resumen separado por: redes con saldo, redes vacías y redes sin conexión."
    ),
    tags=["Testnet"],
)
def testnet_scan(_: str = Depends(verify_api_key)):
    return scan_all_balances()


@app.get(
    "/testnet/balance",
    summary="Balance de la wallet del servidor (testnet)",
    description="Retorna el balance de la wallet configurada en wallet.env para pagar gas.",
    tags=["Testnet"],
)
def testnet_balance(
    network: str = Query("Base Sepolia (testnet)", description="Red testnet"),
    _: str = Depends(verify_api_key),
):
    result = get_testnet_balance(network)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post(
    "/testnet/send",
    summary="Enviar ETH/MATIC real en testnet",
    description=(
        "Firma y envía una transacción nativa real en la testnet elegida. "
        "Usa la PRIVATE_KEY de wallet.env. Solo funciona si la wallet tiene ETH de faucet."
    ),
    tags=["Testnet"],
)
def testnet_send(body: SendTxRequest, _: str = Depends(verify_api_key)):
    result = send_native_token(body.to, body.amount, body.network)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get(
    "/testnet/tx/{tx_hash}",
    summary="Estado de una transacción",
    description="Consulta si una tx fue confirmada, cuánto gas usó y en qué bloque quedó.",
    tags=["Testnet"],
)
def testnet_tx_status(
    tx_hash: str,
    network: str = Query("Base Sepolia (testnet)"),
    _: str = Depends(verify_api_key),
):
    result = get_tx_status(tx_hash, network)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ─── HEALTH ──────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def root():
    return {"status": "ok", "service": "Crypto Payments API", "version": "0.1.0"}

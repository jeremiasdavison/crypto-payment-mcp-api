"""
Crypto MCP Server
Servidor MCP para operaciones cripto: balances, pagos, precios y P&L.

Uso:
    python mcp_server.py              # stdio (para Claude Desktop / claude CLI)
    mcp dev mcp_server.py             # modo desarrollo con inspector

Configuración en claude_desktop_config.json:
    {
      "mcpServers": {
        "crypto": {
          "command": "python",
          "args": ["C:/ruta/al/mcp_server.py"],
          "env": { "WALLET_ENV": "wallet.env" }
        }
      }
    }
"""
import os
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv("wallet.env")

from tools.wallet_tools import (
    consultar_balance_onchain,
    consultar_balance_todas_las_redes,
    crear_nueva_wallet,
    REDES,
)
from tools.payment_tools import preparar_transaccion, ejecutar_pago
from tools.price_tools import get_token_price, get_profit_index, get_multi_price
from tools.tx_tools import scan_all_balances

mcp = FastMCP(
    name="crypto-payments",
    instructions=(
        "Servidor MCP para operaciones cripto en redes EVM. "
        "Permite consultar balances on-chain, precios de tokens, P&L de posiciones, "
        "preparar y simular pagos en Base Sepolia, Polygon y Amoy Testnet."
    ),
)


# ─── BALANCES ────────────────────────────────────────────────────────────────

@mcp.tool()
def get_balance(address: str, network: str = "Base Sepolia (testnet)") -> dict:
    """
    Consulta el balance nativo (ETH o MATIC) de una dirección en una red EVM.

    Args:
        address: Dirección Ethereum (0x...). Debe ser una dirección válida de 42 caracteres.
        network: Red a consultar. Opciones: "Base Sepolia (testnet)", "Polygon Mainnet", "Amoy Testnet (Polygon)".
    """
    return consultar_balance_onchain(address, network)


@mcp.tool()
def get_balance_all_networks(address: str) -> dict:
    """
    Consulta el balance nativo de una dirección en todas las redes configuradas
    (Base Sepolia, Polygon Mainnet y Amoy Testnet) en paralelo.

    Args:
        address: Dirección Ethereum (0x...).
    """
    return consultar_balance_todas_las_redes(address)


@mcp.tool()
def list_networks() -> dict:
    """Lista todas las redes EVM disponibles en el servidor."""
    return {"networks": list(REDES.keys())}


# ─── PRECIOS Y P&L ───────────────────────────────────────────────────────────

@mcp.tool()
def get_price(token: str, currency: str = "usd") -> dict:
    """
    Obtiene el precio actual de un token cripto y su variación en 24h.

    Args:
        token: Símbolo del token. Ej: ETH, BTC, MATIC, USDC, USDT, BNB, SOL, ARB, OP, LINK, UNI, AAVE.
        currency: Moneda de referencia (usd, eur, ars). Por defecto: usd.
    """
    return get_token_price(token, currency)


@mcp.tool()
def get_prices(tokens: list[str], currency: str = "usd") -> dict:
    """
    Obtiene precios actuales de múltiples tokens en una sola consulta.

    Args:
        tokens: Lista de símbolos. Ej: ["ETH", "BTC", "MATIC"].
        currency: Moneda de referencia (usd, eur, ars). Por defecto: usd.
    """
    return get_multi_price(tokens, currency)


@mcp.tool()
def get_profit(
    token: str,
    entry_price: float,
    amount: float,
    currency: str = "usd",
) -> dict:
    """
    Calcula el rendimiento (P&L) de una posición cripto comparando
    el precio de entrada con el precio actual.

    Args:
        token: Símbolo del token. Ej: ETH, BTC, SOL.
        entry_price: Precio de compra en la moneda de referencia.
        amount: Cantidad de tokens en la posición.
        currency: Moneda de referencia (usd, eur). Por defecto: usd.

    Returns:
        Valor de entrada, valor actual, ganancia/pérdida absoluta y porcentual.
    """
    return get_profit_index(token, entry_price, amount, currency)


# ─── PAGOS ───────────────────────────────────────────────────────────────────

@mcp.tool()
def prepare_payment(destination: str, amount: float, token: str = "USDC") -> dict:
    """
    Prepara una transacción cripto sin ejecutarla. Muestra los detalles
    y el gas estimado para revisión antes de confirmar.

    Args:
        destination: Dirección de destino (0x...) o nombre ENS (.eth).
        amount: Monto a enviar (debe ser positivo).
        token: Token a enviar. Ej: USDC, ETH, USDT. Por defecto: USDC.
    """
    if amount <= 0:
        return {"error": "El monto debe ser mayor a 0"}
    return preparar_transaccion(destination, amount, token)


@mcp.tool()
def send_payment(destination: str, amount: float, token: str = "USDC") -> dict:
    """
    Prepara y ejecuta un pago cripto. Actualmente corre en modo simulación (dry_run).
    En la próxima versión se conectará a ZeroDev para transacciones reales.

    Args:
        destination: Dirección de destino (0x...) o nombre ENS (.eth).
        amount: Monto a enviar (debe ser positivo).
        token: Token a enviar. Ej: USDC, ETH, USDT. Por defecto: USDC.
    """
    if amount <= 0:
        return {"error": "El monto debe ser mayor a 0"}
    user_op = preparar_transaccion(destination, amount, token)
    if "error" in user_op:
        return user_op
    return ejecutar_pago(user_op, dry_run=True)


# ─── SCAN ────────────────────────────────────────────────────────────────────

@mcp.tool()
def scan_testnet_balances() -> dict:
    """
    Escanea todas las redes testnet y muestra los saldos de cada wallet.
    Retorna separado: redes con saldo, redes vacías y redes sin conexión.
    Útil para saber dónde tenés fondos de faucet disponibles.
    """
    return scan_all_balances()


# ─── WALLET ──────────────────────────────────────────────────────────────────

@mcp.tool()
def create_wallet() -> dict:
    """
    Genera una nueva wallet EVM (compatible con Ethereum, Polygon, Base, etc.).
    Retorna la dirección pública y la clave privada.
    IMPORTANTE: guarda la private key de forma segura, nunca la compartas.
    """
    return crear_nueva_wallet()


# ─── ENTRY POINT ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()

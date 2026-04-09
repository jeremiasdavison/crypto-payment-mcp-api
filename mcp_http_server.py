from __future__ import annotations
from contextlib import asynccontextmanager
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

import json
import os
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

import mcp.types as types
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel, ConfigDict, Field, ValidationError

load_dotenv("wallet.env")

from tools.networks import ALL_NETWORKS
from tools.payment_tools import ejecutar_pago, preparar_transaccion
from tools.price_tools import get_multi_price, get_profit_index
from tools.tx_tools import get_testnet_balance, get_tx_status, scan_all_balances, send_native_token
from tools.wallet_tools import consultar_balance_onchain, consultar_balance_todas_las_redes, crear_nueva_wallet

# ── WIDGETS ──────────────────────────────────────────────────────────────────────

WIDGETS_DIR = Path(__file__).resolve().parent / "widgets"
MIME_TYPE = "text/html+skybridge"


@dataclass(frozen=True)
class CryptoWidget:
    identifier: str
    title: str
    template_uri: str
    invoking: str
    invoked: str
    html: str


@lru_cache(maxsize=None)
def _load_widget_html(name: str) -> str:
    path = WIDGETS_DIR / f"{name}.html"
    if path.exists():
        return path.read_text(encoding="utf-8")
    raise FileNotFoundError(
        f"Widget '{name}.html' not found in {WIDGETS_DIR}. "
        "Make sure the widgets/ folder exists."
    )


widgets: List[CryptoWidget] = [
    CryptoWidget(
        identifier="scan_testnet_balances",
        title="Scan Testnet Balances",
        template_uri="ui://widget/balance.html",
        invoking="Scanning testnet wallets...",
        invoked="Balance scan complete",
        html=_load_widget_html("balance"),
    ),
    CryptoWidget(
        identifier="get_prices",
        title="Show Token Prices",
        template_uri="ui://widget/prices.html",
        invoking="Fetching crypto prices...",
        invoked="Prices loaded",
        html=_load_widget_html("prices"),
    ),
    CryptoWidget(
        identifier="get_profit",
        title="P&L Dashboard",
        template_uri="ui://widget/profit.html",
        invoking="Calculating P&L...",
        invoked="P&L ready",
        html=_load_widget_html("profit"),
    ),
    CryptoWidget(
        identifier="prepare_payment",
        title="Review Payment",
        template_uri="ui://widget/payment.html",
        invoking="Preparing payment...",
        invoked="Payment ready for review",
        html=_load_widget_html("payment"),
    ),
]

WIDGETS_BY_ID: Dict[str, CryptoWidget] = {w.identifier: w for w in widgets}
WIDGETS_BY_URI: Dict[str, CryptoWidget] = {w.template_uri: w for w in widgets}


# ── INPUT MODELS ─────────────────────────────────────────────────────────────────

class BalanceInput(BaseModel):
    address: str = Field(..., description="Ethereum address (0x...)")
    network: str = Field(default="Base Sepolia (testnet)", description="Network name")
    model_config = ConfigDict(extra="forbid")


class BalanceAllInput(BaseModel):
    address: str = Field(..., description="Ethereum address (0x...)")
    model_config = ConfigDict(extra="forbid")


class TestnetBalanceInput(BaseModel):
    network: str = Field(default="Base Sepolia (testnet)", description="Testnet network name")
    model_config = ConfigDict(extra="forbid")


class SendTestnetInput(BaseModel):
    to: str = Field(..., description="Destination address (0x...)")
    amount: float = Field(..., description="Amount in ETH/MATIC", gt=0)
    network: str = Field(default="Base Sepolia (testnet)", description="Testnet network name")
    model_config = ConfigDict(extra="forbid")


class TxStatusInput(BaseModel):
    tx_hash: str = Field(..., description="Transaction hash (0x...)")
    network: str = Field(default="Base Sepolia (testnet)", description="Network name")
    model_config = ConfigDict(extra="forbid")


class SendPaymentInput(BaseModel):
    destination: str = Field(..., description="Destination address (0x...) or ENS (.eth)")
    amount: float = Field(..., description="Amount to send", gt=0)
    token: str = Field(default="USDC", description="Token: USDC, ETH, USDT")
    model_config = ConfigDict(extra="forbid")


class PricesInput(BaseModel):
    tokens: List[str] = Field(..., description="Token symbols. E.g.: ['ETH', 'BTC', 'SOL']")
    currency: str = Field(default="usd", description="Reference currency: usd, eur, ars")
    model_config = ConfigDict(extra="forbid")


class ProfitInput(BaseModel):
    token: str = Field(..., description="Token symbol. E.g.: ETH, BTC, SOL")
    entry_price: float = Field(..., alias="entryPrice", description="Purchase price in USD", gt=0)
    amount: float = Field(..., description="Number of tokens held", gt=0)
    currency: str = Field(default="usd")
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class PaymentInput(BaseModel):
    destination: str = Field(..., description="Destination address (0x...) or ENS (.eth)")
    amount: float = Field(..., description="Amount to send", gt=0)
    token: str = Field(default="USDC", description="Token: USDC, ETH, USDT")
    model_config = ConfigDict(extra="forbid")


# ── JSON SCHEMAS FOR MCP TOOL REGISTRATION ───────────────────────────────────────

BALANCE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "address": {"type": "string", "description": "Ethereum address (0x...)"},
        "network": {
            "type": "string",
            "description": "Network name. E.g.: Base Sepolia (testnet), Polygon Mainnet",
            "default": "Base Sepolia (testnet)",
        },
    },
    "required": ["address"],
    "additionalProperties": False,
}

BALANCE_ALL_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "address": {"type": "string", "description": "Ethereum address (0x...)"},
    },
    "required": ["address"],
    "additionalProperties": False,
}

LIST_NETWORKS_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}

CREATE_WALLET_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}

TESTNET_BALANCE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "network": {
            "type": "string",
            "description": "Testnet network name",
            "default": "Base Sepolia (testnet)",
        },
    },
    "additionalProperties": False,
}

SEND_TESTNET_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "to": {"type": "string", "description": "Destination address (0x...)"},
        "amount": {
            "type": "number",
            "description": "Amount in ETH/MATIC (not wei)",
            "exclusiveMinimum": 0,
        },
        "network": {
            "type": "string",
            "description": "Testnet network name",
            "default": "Base Sepolia (testnet)",
        },
    },
    "required": ["to", "amount"],
    "additionalProperties": False,
}

TX_STATUS_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "tx_hash": {"type": "string", "description": "Transaction hash (0x...)"},
        "network": {
            "type": "string",
            "description": "Network name",
            "default": "Base Sepolia (testnet)",
        },
    },
    "required": ["tx_hash"],
    "additionalProperties": False,
}

SEND_PAYMENT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "destination": {
            "type": "string",
            "description": "Destination address (0x...) or ENS name (.eth)",
        },
        "amount": {
            "type": "number",
            "description": "Amount to send",
            "exclusiveMinimum": 0,
        },
        "token": {
            "type": "string",
            "description": "Token to send: USDC, ETH, USDT",
            "default": "USDC",
        },
    },
    "required": ["destination", "amount"],
    "additionalProperties": False,
}

SCAN_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}

PRICES_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "tokens": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Token symbols. E.g.: ['ETH', 'BTC', 'SOL']",
        },
        "currency": {
            "type": "string",
            "description": "Reference currency: usd, eur, ars",
            "default": "usd",
        },
    },
    "required": ["tokens"],
    "additionalProperties": False,
}

PROFIT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "token": {"type": "string", "description": "Token symbol. E.g.: ETH, BTC, SOL"},
        "entryPrice": {
            "type": "number",
            "description": "Purchase price in USD",
            "exclusiveMinimum": 0,
        },
        "amount": {
            "type": "number",
            "description": "Number of tokens held",
            "exclusiveMinimum": 0,
        },
        "currency": {
            "type": "string",
            "description": "Reference currency (usd, eur)",
            "default": "usd",
        },
    },
    "required": ["token", "entryPrice", "amount"],
    "additionalProperties": False,
}

PAYMENT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "destination": {
            "type": "string",
            "description": "Destination address (0x...) or ENS name (.eth)",
        },
        "amount": {
            "type": "number",
            "description": "Amount to send",
            "exclusiveMinimum": 0,
        },
        "token": {
            "type": "string",
            "description": "Token to send: USDC, ETH, USDT",
            "default": "USDC",
        },
    },
    "required": ["destination", "amount"],
    "additionalProperties": False,
}


# ── TRANSPORT SECURITY ────────────────────────────────────────────────────────────

def _split_env_list(value: str | None) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _transport_security() -> TransportSecuritySettings:
    allowed_hosts = _split_env_list(os.getenv("MCP_ALLOWED_HOSTS"))
    allowed_origins = _split_env_list(os.getenv("MCP_ALLOWED_ORIGINS"))
    if not allowed_hosts and not allowed_origins:
        return TransportSecuritySettings(enable_dns_rebinding_protection=False)
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )


# ── MCP SERVER ────────────────────────────────────────────────────────────────────

mcp = FastMCP(
    name="crypto-payments",
    instructions=(
        "MCP server for EVM crypto operations with native ChatGPT UI. "
        "Provides real-time testnet balances, token prices, P&L calculations "
        "and payment preparation with interactive visual widgets."
    ),
    stateless_http=True,
    transport_security=_transport_security(),
)


# ── META HELPERS ──────────────────────────────────────────────────────────────────

def _tool_meta(widget: CryptoWidget) -> Dict[str, Any]:
    return {
        "openai/outputTemplate": widget.template_uri,
        "openai/toolInvocation/invoking": widget.invoking,
        "openai/toolInvocation/invoked": widget.invoked,
        "openai/widgetAccessible": True,
    }


def _invocation_meta(widget: CryptoWidget) -> Dict[str, Any]:
    return {
        "openai/outputTemplate": widget.template_uri,
        "openai/toolInvocation/invoking": widget.invoking,
        "openai/toolInvocation/invoked": widget.invoked,
        "openai/widgetAccessible": True,
    }


def _resource_meta(widget: CryptoWidget) -> Dict[str, Any]:
    return {
        "openai/outputTemplate": widget.template_uri,
        "openai/widgetDescription": widget.title,
        "openai/widgetPrefersBorder": True,
        "openai/widgetAccessible": True,
        "openai/widgetCSP": {
            "connect_domains": [],
            "resource_domains": [],
        },
    }


def _safe_json_text(data: Dict[str, Any]) -> str:
    try:
        return json.dumps(data, ensure_ascii=False, indent=2)
    except Exception:
        return "{}"


# ── UI NORMALIZERS ────────────────────────────────────────────────────────────────

def _normalize_scan_result(data: Dict[str, Any]) -> Dict[str, Any]:
    resumen = data.get("resumen", {}) or {}
    return {
        "summary": {
            "totalNetworks": resumen.get("total_redes", 0),
            "withFunds": resumen.get("redes_con_saldo", 0),
            "empty": resumen.get("redes_vacias", 0),
            "offline": resumen.get("redes_sin_conexion", 0),
        },
        "walletsWithFunds": data.get("con_saldo", []) or [],
        "emptyWallets": data.get("vacias", []) or [],
        "offlineWallets": data.get("sin_conexion", []) or [],
        "raw": data,
    }


def _normalize_prices_result(data: Dict[str, Any], tokens: List[str], currency: str) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []

    if isinstance(data.get("prices"), dict):
        for symbol, info in data["prices"].items():
            info = info or {}
            items.append(
                {
                    "symbol": symbol,
                    "price": info.get("price"),
                    "change24h": info.get("change_24h_pct"),
                    "currency": info.get("currency", currency),
                }
            )
    elif data.get("token") and data.get("price") is not None:
        items.append(
            {
                "symbol": data.get("token"),
                "price": data.get("price"),
                "change24h": data.get("change_24h_pct"),
                "currency": data.get("currency", currency),
            }
        )

    return {
        "currency": (data.get("currency") or currency or "usd").upper(),
        "items": items,
        "source": data.get("source"),
        "timestamp": data.get("timestamp"),
        "requestedTokens": tokens,
        "raw": data,
    }


def _normalize_profit_result(data: Dict[str, Any], inp: ProfitInput) -> Dict[str, Any]:
    return {
        "token": inp.token,
        "amount": inp.amount,
        "currency": (data.get("currency") or inp.currency or "usd").upper(),
        "entryPrice": data.get("entry_price", inp.entry_price),
        "currentPrice": data.get("current_price"),
        "entryValue": data.get("entry_value"),
        "currentValue": data.get("current_value"),
        "pnlValue": data.get("pnl"),
        "pnlPct": data.get("pnl_pct"),
        "change24h": data.get("change_24h_pct"),
        "raw": data,
    }


def _normalize_payment_result(data: Dict[str, Any], inp: PaymentInput) -> Dict[str, Any]:
    return {
        "destination": data.get("to") or inp.destination,
        "resolvedAddress": data.get("to"),
        "originalDestination": data.get("to_original") or inp.destination,
        "amount": data.get("amount", inp.amount),
        "token": data.get("token", inp.token),
        "estimatedGas": data.get("estimated_gas"),
        "network": data.get("network"),
        "status": "review",
        "raw": data,
    }


# ── TOOL + RESOURCE REGISTRATION ─────────────────────────────────────────────────

@mcp._mcp_server.list_tools()
async def _list_tools() -> List[types.Tool]:
    return [
        types.Tool(
            name="scan_testnet_balances",
            title="Scan Testnet Balances",
            description=(
                "Scan all testnet wallet addresses and display balances across "
                "6 EVM networks (Base, Ethereum, Optimism, Arbitrum, Polygon, Scroll) "
                "in an interactive dashboard."
            ),
            inputSchema=deepcopy(SCAN_SCHEMA),
            _meta=_tool_meta(WIDGETS_BY_ID["scan_testnet_balances"]),
            annotations={"destructiveHint": False, "openWorldHint": False, "readOnlyHint": True},
        ),
        types.Tool(
            name="get_prices",
            title="Get Token Prices",
            description=(
                "Fetch real-time prices for multiple crypto tokens with 24h change. "
                "Supported: BTC, ETH, MATIC, POL, USDC, USDT, BNB, SOL, ARB, OP, LINK, UNI, AAVE."
            ),
            inputSchema=deepcopy(PRICES_SCHEMA),
            _meta=_tool_meta(WIDGETS_BY_ID["get_prices"]),
            annotations={"destructiveHint": False, "openWorldHint": True, "readOnlyHint": True},
        ),
        types.Tool(
            name="get_profit",
            title="Calculate P&L",
            description=(
                "Calculate profit and loss for a crypto position. "
                "Compares entry price against current market price."
            ),
            inputSchema=deepcopy(PROFIT_SCHEMA),
            _meta=_tool_meta(WIDGETS_BY_ID["get_profit"]),
            annotations={"destructiveHint": False, "openWorldHint": True, "readOnlyHint": True},
        ),
        types.Tool(
            name="prepare_payment",
            title="Prepare Payment",
            description=(
                "Prepare a crypto payment for review. "
                "Shows destination address, amount, token and estimated gas before confirming."
            ),
            inputSchema=deepcopy(PAYMENT_SCHEMA),
            _meta=_tool_meta(WIDGETS_BY_ID["prepare_payment"]),
            annotations={"destructiveHint": False, "openWorldHint": False, "readOnlyHint": False},
        ),
        types.Tool(
            name="get_balance",
            title="Get Wallet Balance",
            description=(
                "Get the native token balance (ETH or MATIC) of any wallet address on a specific network. "
                "Supports all configured testnets and mainnets."
            ),
            inputSchema=deepcopy(BALANCE_SCHEMA),
            annotations={"destructiveHint": False, "openWorldHint": False, "readOnlyHint": True},
        ),
        types.Tool(
            name="get_balance_all_networks",
            title="Get Balance on All Networks",
            description="Get the native token balance of a wallet address across all configured networks at once.",
            inputSchema=deepcopy(BALANCE_ALL_SCHEMA),
            annotations={"destructiveHint": False, "openWorldHint": False, "readOnlyHint": True},
        ),
        types.Tool(
            name="list_networks",
            title="List Available Networks",
            description="List all supported EVM networks (testnets and mainnets).",
            inputSchema=deepcopy(LIST_NETWORKS_SCHEMA),
            annotations={"destructiveHint": False, "openWorldHint": False, "readOnlyHint": True},
        ),
        types.Tool(
            name="create_wallet",
            title="Create New Wallet",
            description=(
                "Generate a new EVM-compatible wallet (address + private key). "
                "WARNING: save the private key securely — never share it."
            ),
            inputSchema=deepcopy(CREATE_WALLET_SCHEMA),
            annotations={"destructiveHint": False, "openWorldHint": False, "readOnlyHint": False},
        ),
        types.Tool(
            name="get_testnet_balance",
            title="Get Server Wallet Balance (Testnet)",
            description="Get the balance of the server's configured wallet on a testnet. Used to check gas funds.",
            inputSchema=deepcopy(TESTNET_BALANCE_SCHEMA),
            annotations={"destructiveHint": False, "openWorldHint": False, "readOnlyHint": True},
        ),
        types.Tool(
            name="send_testnet_payment",
            title="Send Native Token (Testnet)",
            description=(
                "Sign and send a real native token transfer (ETH or MATIC) on a testnet. "
                "Uses the server wallet configured in wallet.env. Requires faucet funds."
            ),
            inputSchema=deepcopy(SEND_TESTNET_SCHEMA),
            annotations={"destructiveHint": True, "openWorldHint": False, "readOnlyHint": False},
        ),
        types.Tool(
            name="get_tx_status",
            title="Get Transaction Status",
            description="Check if a transaction was confirmed, how much gas it used, and which block it landed in.",
            inputSchema=deepcopy(TX_STATUS_SCHEMA),
            annotations={"destructiveHint": False, "openWorldHint": False, "readOnlyHint": True},
        ),
        types.Tool(
            name="send_payment",
            title="Send Payment (Simulation)",
            description=(
                "Prepare and simulate a crypto payment (dry-run mode). "
                "Returns what would be sent without executing a real transaction."
            ),
            inputSchema=deepcopy(SEND_PAYMENT_SCHEMA),
            annotations={"destructiveHint": False, "openWorldHint": False, "readOnlyHint": False},
        ),
    ]


@mcp._mcp_server.list_resources()
async def _list_resources() -> List[types.Resource]:
    return [
        types.Resource(
            name=w.identifier,
            title=w.title,
            uri=w.template_uri,
            description=f"{w.title} widget",
            mimeType=MIME_TYPE,
            _meta=_resource_meta(w),
        )
        for w in widgets
    ]


@mcp._mcp_server.list_resource_templates()
async def _list_resource_templates() -> List[types.ResourceTemplate]:
    return [
        types.ResourceTemplate(
            name=w.identifier,
            title=w.title,
            uriTemplate=w.template_uri,
            description=f"{w.title} widget",
            mimeType=MIME_TYPE,
            _meta=_resource_meta(w),
        )
        for w in widgets
    ]


async def _handle_read_resource(req: types.ReadResourceRequest) -> types.ServerResult:
    widget = WIDGETS_BY_URI.get(str(req.params.uri))
    if widget is None:
        return types.ServerResult(
            types.ReadResourceResult(
                contents=[],
                _meta={"error": f"Unknown resource: {req.params.uri}"},
            )
        )

    return types.ServerResult(
        types.ReadResourceResult(
            contents=[
                types.TextResourceContents(
                    uri=widget.template_uri,
                    mimeType=MIME_TYPE,
                    text=widget.html,
                    _meta=_resource_meta(widget),
                )
            ]
        )
    )


async def _call_tool_request(req: types.CallToolRequest) -> types.ServerResult:
    name = req.params.name
    args = req.params.arguments or {}

    try:
        if name == "scan_testnet_balances":
            raw_data = scan_all_balances()
            widget = WIDGETS_BY_ID["scan_testnet_balances"]
            ui_data = _normalize_scan_result(raw_data)
            s = ui_data["summary"]

            return types.ServerResult(
                types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text",
                            text=(
                                f"Scanned {s.get('totalNetworks', 0)} networks. "
                                f"{s.get('withFunds', 0)} with funds, "
                                f"{s.get('empty', 0)} empty, "
                                f"{s.get('offline', 0)} offline."
                            ),
                        )
                    ],
                    structuredContent=ui_data,
                    _meta=_invocation_meta(widget),
                )
            )

        elif name == "get_prices":
            inp = PricesInput.model_validate(args)
            raw_data = get_multi_price(inp.tokens, inp.currency)
            widget = WIDGETS_BY_ID["get_prices"]
            ui_data = _normalize_prices_result(raw_data, inp.tokens, inp.currency)

            return types.ServerResult(
                types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text",
                            text=f"Prices loaded for: {', '.join(inp.tokens)}",
                        )
                    ],
                    structuredContent=ui_data,
                    _meta=_invocation_meta(widget),
                )
            )

        elif name == "get_profit":
            inp = ProfitInput.model_validate(args)
            raw_data = get_profit_index(inp.token, inp.entry_price, inp.amount, inp.currency)
            widget = WIDGETS_BY_ID["get_profit"]
            ui_data = _normalize_profit_result(raw_data, inp)
            pnl_pct = ui_data.get("pnlPct") or 0

            return types.ServerResult(
                types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text",
                            text=f"P&L for {inp.amount} {inp.token}: {pnl_pct:+.2f}%",
                        )
                    ],
                    structuredContent=ui_data,
                    _meta=_invocation_meta(widget),
                )
            )

        elif name == "prepare_payment":
            inp = PaymentInput.model_validate(args)
            raw_data = preparar_transaccion(inp.destination, inp.amount, inp.token)
            widget = WIDGETS_BY_ID["prepare_payment"]
            ui_data = _normalize_payment_result(raw_data, inp)

            return types.ServerResult(
                types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text",
                            text=(
                                f"Payment ready: "
                                f"{ui_data.get('amount')} {ui_data.get('token')} "
                                f"→ {ui_data.get('originalDestination')}"
                            ),
                        )
                    ],
                    structuredContent=ui_data,
                    _meta=_invocation_meta(widget),
                )
            )

        elif name == "get_balance":
            inp = BalanceInput.model_validate(args)
            raw_data = consultar_balance_onchain(inp.address, inp.network)
            if "error" in raw_data:
                return types.ServerResult(
                    types.CallToolResult(
                        content=[types.TextContent(type="text", text=raw_data["error"])],
                        structuredContent=raw_data,
                        isError=True,
                    )
                )
            return types.ServerResult(
                types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text",
                            text=f"Balance: {raw_data['balance']} {raw_data['token']} on {raw_data['red']}",
                        )
                    ],
                    structuredContent=raw_data,
                )
            )

        elif name == "get_balance_all_networks":
            inp = BalanceAllInput.model_validate(args)
            raw_data = consultar_balance_todas_las_redes(inp.address)
            if "error" in raw_data:
                return types.ServerResult(
                    types.CallToolResult(
                        content=[types.TextContent(type="text", text=raw_data["error"])],
                        structuredContent=raw_data,
                        isError=True,
                    )
                )
            networks_with_balance = [
                f"{net}: {info.get('balance', 0)} {info.get('token', '')}"
                for net, info in raw_data.items()
                if isinstance(info, dict) and not info.get("error") and info.get("balance", 0) > 0
            ]
            summary = ", ".join(networks_with_balance) if networks_with_balance else "No funds found"
            return types.ServerResult(
                types.CallToolResult(
                    content=[types.TextContent(type="text", text=f"Balances for {inp.address}: {summary}")],
                    structuredContent=raw_data,
                )
            )

        elif name == "list_networks":
            networks = list(ALL_NETWORKS.keys())
            return types.ServerResult(
                types.CallToolResult(
                    content=[types.TextContent(type="text", text=f"Available networks: {', '.join(networks)}")],
                    structuredContent={"networks": networks},
                )
            )

        elif name == "create_wallet":
            raw_data = crear_nueva_wallet()
            return types.ServerResult(
                types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text",
                            text=f"New wallet created: {raw_data['address']}. Save the private key securely.",
                        )
                    ],
                    structuredContent=raw_data,
                )
            )

        elif name == "get_testnet_balance":
            inp = TestnetBalanceInput.model_validate(args)
            raw_data = get_testnet_balance(inp.network)
            if "error" in raw_data:
                return types.ServerResult(
                    types.CallToolResult(
                        content=[types.TextContent(type="text", text=raw_data["error"])],
                        structuredContent=raw_data,
                        isError=True,
                    )
                )
            return types.ServerResult(
                types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text",
                            text=f"Server wallet balance: {raw_data['balance']} {raw_data['token']} on {raw_data['network']}",
                        )
                    ],
                    structuredContent=raw_data,
                )
            )

        elif name == "send_testnet_payment":
            inp = SendTestnetInput.model_validate(args)
            raw_data = send_native_token(inp.to, inp.amount, inp.network)
            if "error" in raw_data:
                return types.ServerResult(
                    types.CallToolResult(
                        content=[types.TextContent(type="text", text=raw_data["error"])],
                        structuredContent=raw_data,
                        isError=True,
                    )
                )
            return types.ServerResult(
                types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text",
                            text=f"Sent {raw_data['amount']} {raw_data['token']} → {raw_data['to']}. Tx: {raw_data['tx_hash']}",
                        )
                    ],
                    structuredContent=raw_data,
                )
            )

        elif name == "get_tx_status":
            inp = TxStatusInput.model_validate(args)
            raw_data = get_tx_status(inp.tx_hash, inp.network)
            if "error" in raw_data:
                return types.ServerResult(
                    types.CallToolResult(
                        content=[types.TextContent(type="text", text=raw_data["error"])],
                        structuredContent=raw_data,
                        isError=True,
                    )
                )
            return types.ServerResult(
                types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text",
                            text=f"Transaction {inp.tx_hash}: {raw_data['status']}",
                        )
                    ],
                    structuredContent=raw_data,
                )
            )

        elif name == "send_payment":
            inp = SendPaymentInput.model_validate(args)
            user_op = preparar_transaccion(inp.destination, inp.amount, inp.token)
            if "error" in user_op:
                return types.ServerResult(
                    types.CallToolResult(
                        content=[types.TextContent(type="text", text=user_op["error"])],
                        structuredContent=user_op,
                        isError=True,
                    )
                )
            raw_data = ejecutar_pago(user_op, dry_run=True)
            return types.ServerResult(
                types.CallToolResult(
                    content=[types.TextContent(type="text", text=raw_data["message"])],
                    structuredContent=raw_data,
                )
            )

        else:
            return types.ServerResult(
                types.CallToolResult(
                    content=[types.TextContent(type="text", text=f"Unknown tool: {name}")],
                    isError=True,
                )
            )

    except ValidationError as exc:
        return types.ServerResult(
            types.CallToolResult(
                content=[types.TextContent(type="text", text=f"Input error: {exc.errors()}")],
                structuredContent={"error": "validation_error", "details": exc.errors()},
                isError=True,
            )
        )
    except Exception as exc:
        return types.ServerResult(
            types.CallToolResult(
                content=[types.TextContent(type="text", text=f"Error: {exc}")],
                structuredContent={"error": str(exc)},
                isError=True,
            )
        )


mcp._mcp_server.request_handlers[types.CallToolRequest] = _call_tool_request
mcp._mcp_server.request_handlers[types.ReadResourceRequest] = _handle_read_resource


# ── HTTP APP ──────────────────────────────────────────────────────────────────────
streamable_app = mcp.streamable_http_app()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Trigger the MCP streamable app lifespan so its task group is initialized
    async with streamable_app.router.lifespan_context(app):
        yield


app = FastAPI(title="Crypto Payments MCP", redirect_slashes=False, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)


@app.get("/")
async def mcp_root():
    return {
        "status": "ok",
        "service": "crypto-payments-mcp",
        "transport": "streamable-http",
    }


@app.get("/health")
async def mcp_health():
    return {
        "status": "ok",
        "service": "crypto-payments-mcp",
    }


app.mount("/", streamable_app)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("mcp_http_server:app", host="0.0.0.0", port=8001)
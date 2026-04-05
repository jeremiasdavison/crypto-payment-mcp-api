import secrets
from eth_account import Account
from web3 import Web3


# ─── Redes soportadas ────────────────────────────────────────────────────────

REDES = {
    "Base Sepolia (testnet)": "https://sepolia.base.org",
    "Polygon Mainnet": "https://polygon-rpc.com",
    "Amoy Testnet (Polygon)": "https://rpc-amoy.polygon.technology",
}


def consultar_balance_onchain(address: str, red: str = "Base Sepolia (testnet)") -> dict:
    """
    Consulta el balance nativo (ETH/MATIC) de una dirección en la red elegida.
    En Fase 2 se expandirá para leer tokens ERC-20 (USDC) via Alchemy.
    """
    if not Web3.is_address(address):
        return {"error": f"Dirección inválida: {address}"}

    rpc_url = REDES.get(red)
    if not rpc_url:
        redes_disponibles = list(REDES.keys())
        return {"error": f"Red desconocida. Opciones: {redes_disponibles}"}

    try:
        web3 = Web3(Web3.HTTPProvider(rpc_url))
        if not web3.is_connected():
            return {"error": f"Sin conexión a {red}"}

        balance_wei = web3.eth.get_balance(address)
        balance = float(web3.from_wei(balance_wei, "ether"))

        token_nativo = "MATIC" if "Polygon" in red or "Amoy" in red else "ETH"

        return {
            "address": address,
            "balance": round(balance, 6),
            "token": token_nativo,
            "red": red,
            "source": "onchain",
        }
    except Exception as e:
        return {"error": str(e)}


def consultar_balance_todas_las_redes(address: str) -> dict:
    """Consulta el balance en todas las redes configuradas."""
    if not Web3.is_address(address):
        return {"error": f"Dirección inválida: {address}"}

    resultados = {}
    for nombre_red in REDES:
        resultado = consultar_balance_onchain(address, nombre_red)
        resultados[nombre_red] = resultado
    return resultados


def crear_nueva_wallet() -> dict:
    """
    Genera una nueva wallet Ethereum (compatible con cualquier EVM chain).
    IMPORTANTE: guardar la private key de forma segura, nunca subirla a git.
    """
    private_key = "0x" + secrets.token_hex(32)
    account = Account.from_key(private_key)

    return {
        "address": account.address,
        "private_key": private_key,
        "advertencia": "Guarda la private key en un lugar seguro. NUNCA la compartas ni la subas a git.",
    }

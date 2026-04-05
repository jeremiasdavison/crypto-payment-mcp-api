import secrets
from eth_account import Account
from web3 import Web3

from tools.networks import ALL_NETWORKS, TESTNETS, DEFAULT_TESTNET

# Alias para compatibilidad con api_server.py
REDES = ALL_NETWORKS


def consultar_balance_onchain(address: str, red: str = DEFAULT_TESTNET) -> dict:
    """Consulta el balance nativo (ETH/POL) de una dirección en la red elegida."""
    if not Web3.is_address(address):
        return {"error": f"Dirección inválida: {address}"}

    rpc_url = ALL_NETWORKS.get(red)
    if not rpc_url:
        return {"error": f"Red desconocida. Opciones: {list(ALL_NETWORKS.keys())}"}

    try:
        web3 = Web3(Web3.HTTPProvider(rpc_url))
        if not web3.is_connected():
            return {"error": f"Sin conexión a {red}"}

        balance_wei = web3.eth.get_balance(address)
        balance = float(web3.from_wei(balance_wei, "ether"))

        # Obtener el token nativo desde la config centralizada
        cfg = {**TESTNETS, **{k: {"token": "ETH"} for k in ALL_NETWORKS if k not in TESTNETS}}
        token = cfg.get(red, {}).get("token", "ETH")

        return {
            "address": address,
            "balance": round(balance, 6),
            "token": token,
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
    for nombre_red in ALL_NETWORKS:
        resultados[nombre_red] = consultar_balance_onchain(address, nombre_red)
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

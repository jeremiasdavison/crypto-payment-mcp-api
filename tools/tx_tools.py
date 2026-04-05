"""
Transacciones reales en redes EVM usando web3.py.
Soporta transferencias nativas (ETH/MATIC) en testnets.
La private key se carga desde wallet.env — nunca se hardcodea.
"""
import os
from dotenv import load_dotenv
from web3 import Web3

load_dotenv("wallet.env")

REDES = {
    "Base Sepolia (testnet)": {
        "rpc": "https://sepolia.base.org",
        "chain_id": 84532,
        "token": "ETH",
        "explorer": "https://sepolia.basescan.org/tx",
    },
    "Amoy Testnet (Polygon)": {
        "rpc": "https://rpc-amoy.polygon.technology",
        "chain_id": 80002,
        "token": "MATIC",
        "explorer": "https://amoy.polygonscan.com/tx",
    },
}


def _load_account():
    private_key = os.getenv("PRIVATE_KEY")
    wallet_address = os.getenv("WALLET_ADDRESS")
    if not private_key or not wallet_address:
        raise ValueError("Faltan PRIVATE_KEY o WALLET_ADDRESS en wallet.env")
    return private_key, Web3.to_checksum_address(wallet_address)


def get_testnet_balance(network: str = "Base Sepolia (testnet)") -> dict:
    """Retorna el balance de la wallet configurada en wallet.env."""
    config = REDES.get(network)
    if not config:
        return {"error": f"Red no soportada para txs reales. Opciones: {list(REDES.keys())}"}

    _, address = _load_account()
    web3 = Web3(Web3.HTTPProvider(config["rpc"]))

    if not web3.is_connected():
        return {"error": f"Sin conexión a {network}"}

    balance_wei = web3.eth.get_balance(address)
    balance = float(web3.from_wei(balance_wei, "ether"))

    return {
        "address": address,
        "balance": round(balance, 8),
        "token": config["token"],
        "network": network,
        "has_gas": balance >= 0.0001,
    }


def send_native_token(
    to: str,
    amount_eth: float,
    network: str = "Base Sepolia (testnet)",
) -> dict:
    """
    Envía ETH o MATIC nativo en una red testnet.
    Firma con la PRIVATE_KEY de wallet.env.

    Args:
        to: Dirección destino (0x...)
        amount_eth: Cantidad en ETH/MATIC (no en wei)
        network: Red a usar (solo testnets soportadas)
    """
    config = REDES.get(network)
    if not config:
        return {"error": f"Red no soportada. Opciones: {list(REDES.keys())}"}

    if not Web3.is_address(to):
        return {"error": f"Dirección destino inválida: {to}"}

    if amount_eth <= 0:
        return {"error": "El monto debe ser mayor a 0"}

    try:
        private_key, from_address = _load_account()
        web3 = Web3(Web3.HTTPProvider(config["rpc"]))

        if not web3.is_connected():
            return {"error": f"Sin conexión a {network}"}

        # Verificar balance suficiente
        balance_wei = web3.eth.get_balance(from_address)
        amount_wei = web3.to_wei(amount_eth, "ether")
        gas_price = web3.eth.gas_price
        gas_limit = 21000  # transferencia nativa estándar
        gas_cost = gas_price * gas_limit

        if balance_wei < amount_wei + gas_cost:
            balance_eth = float(web3.from_wei(balance_wei, "ether"))
            needed = float(web3.from_wei(amount_wei + gas_cost, "ether"))
            return {
                "error": f"Balance insuficiente. Tenés {balance_eth:.6f} {config['token']}, necesitás ~{needed:.6f}"
            }

        # Construir la transacción
        nonce = web3.eth.get_transaction_count(from_address)
        tx = {
            "nonce": nonce,
            "to": Web3.to_checksum_address(to),
            "value": amount_wei,
            "gas": gas_limit,
            "gasPrice": gas_price,
            "chainId": config["chain_id"],
        }

        # Firmar y enviar
        signed = web3.eth.account.sign_transaction(tx, private_key)
        tx_hash = web3.eth.send_raw_transaction(signed.raw_transaction)
        tx_hash_hex = tx_hash.hex()

        return {
            "status": "enviado",
            "tx_hash": tx_hash_hex,
            "explorer_url": f"{config['explorer']}/{tx_hash_hex}",
            "from": from_address,
            "to": to,
            "amount": amount_eth,
            "token": config["token"],
            "network": network,
        }

    except Exception as e:
        return {"error": str(e)}


def get_tx_status(tx_hash: str, network: str = "Base Sepolia (testnet)") -> dict:
    """
    Consulta el estado de una transacción por su hash.
    Retorna si fue confirmada, cuánto gas usó y el bloque.
    """
    config = REDES.get(network)
    if not config:
        return {"error": f"Red no soportada"}

    try:
        web3 = Web3(Web3.HTTPProvider(config["rpc"]))
        receipt = web3.eth.get_transaction_receipt(tx_hash)

        if receipt is None:
            return {"status": "pendiente", "tx_hash": tx_hash}

        return {
            "status": "confirmada" if receipt.status == 1 else "fallida",
            "tx_hash": tx_hash,
            "block": receipt.blockNumber,
            "gas_used": receipt.gasUsed,
            "explorer_url": f"{config['explorer']}/{tx_hash}",
        }
    except Exception as e:
        # La mayoría de RPCs lanzan excepción cuando el hash no existe aún
        msg = str(e).lower()
        if "not found" in msg or "does not exist" in msg or "unknown" in msg:
            return {"status": "pendiente", "tx_hash": tx_hash}
        return {"error": str(e)}

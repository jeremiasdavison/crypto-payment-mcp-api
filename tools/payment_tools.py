from typing import Optional


def consultar_balance(token: str, wallet: str) -> dict:
    """Simula consulta de balance. En Fase 2 conecta a Alchemy + web3.py."""
    balances_mock = {
        "USDC": 500.0,
        "ETH": 0.25,
        "USDT": 100.0,
    }
    balance = balances_mock.get(token.upper(), 0.0)
    return {
        "token": token.upper(),
        "balance": balance,
        "wallet": wallet,
        "source": "mock",
    }


def resolver_ens(nombre: str) -> str:
    """Simula resolución ENS. En Fase 2 conecta a ENS real via web3.py."""
    ens_mock = {
        "juan.eth": "0xAbCd1234567890AbCd1234567890AbCd12345678",
        "maria.eth": "0xDeFg5678901234DeFg5678901234DeFg56789012",
    }
    if nombre in ens_mock:
        return ens_mock[nombre]
    # Si no es ENS, asumir dirección directa
    return nombre


def preparar_transaccion(destino: str, monto: float, token: str) -> dict:
    """Prepara una UserOperation (ERC-4337) simulada."""
    if monto <= 0:
        raise ValueError("El monto debe ser positivo")

    direccion = resolver_ens(destino)

    return {
        "type": "UserOperation",
        "to": direccion,
        "to_original": destino,
        "amount": monto,
        "token": token.upper(),
        "estimated_gas": "~$0.01 en Base Sepolia",
        "status": "pendiente_aprobacion",
    }


def ejecutar_pago(user_op: dict, dry_run: bool = True) -> dict:
    """Ejecuta o simula el pago."""
    if dry_run:
        return {
            "status": "dry_run",
            "message": (
                f"[SIMULADO] Se enviarían {user_op['amount']} {user_op['token']} "
                f"a {user_op['to_original']} ({user_op['to']})"
            ),
            "tx_hash": None,
        }
    # Fase 2: acá va la llamada real a ZeroDev con Session Key
    return {
        "status": "ejecutado",
        "tx_hash": "0xMOCK_TX_HASH",
        "message": "Pago enviado (mock)",
    }

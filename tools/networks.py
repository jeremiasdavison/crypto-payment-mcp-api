"""
Configuración central de redes EVM.
Fuente única de verdad — importar desde acá en todos los tools.
"""

# Redes con soporte completo (balance + transacciones)
TESTNETS: dict[str, dict] = {
    "Base Sepolia": {
        "rpc": "https://sepolia.base.org",
        "chain_id": 84532,
        "token": "ETH",
        "explorer": "https://sepolia.basescan.org/tx",
        "faucet": "https://faucet.coinbase.com",
    },
    "Ethereum Sepolia": {
        "rpc": "https://ethereum-sepolia-rpc.publicnode.com",
        "chain_id": 11155111,
        "token": "ETH",
        "explorer": "https://sepolia.etherscan.io/tx",
        "faucet": "https://sepoliafaucet.com",
    },
    "Optimism Sepolia": {
        "rpc": "https://sepolia.optimism.io",
        "chain_id": 11155420,
        "token": "ETH",
        "explorer": "https://sepolia-optimism.etherscan.io/tx",
        "faucet": "https://app.optimism.io/faucet",
    },
    "Arbitrum Sepolia": {
        "rpc": "https://sepolia-rollup.arbitrum.io/rpc",
        "chain_id": 421614,
        "token": "ETH",
        "explorer": "https://sepolia.arbiscan.io/tx",
        "faucet": "https://faucet.triangleplatform.com/arbitrum/sepolia",
    },
    "Polygon Amoy": {
        "rpc": "https://rpc-amoy.polygon.technology",
        "chain_id": 80002,
        "token": "POL",
        "explorer": "https://amoy.polygonscan.com/tx",
        "faucet": "https://faucet.polygon.technology",
    },
    "Scroll Sepolia": {
        "rpc": "https://sepolia-rpc.scroll.io",
        "chain_id": 534351,
        "token": "ETH",
        "explorer": "https://sepolia.scrollscan.com/tx",
        "faucet": "https://docs.scroll.io/en/user-guide/faucet",
    },
}

# Solo para consulta de balance (sin soporte de tx por ahora)
MAINNETS: dict[str, dict] = {
    "Polygon Mainnet": {
        "rpc": "https://polygon-rpc.com",
        "chain_id": 137,
        "token": "POL",
        "explorer": "https://polygonscan.com/tx",
    },
    "Base Mainnet": {
        "rpc": "https://mainnet.base.org",
        "chain_id": 8453,
        "token": "ETH",
        "explorer": "https://basescan.org/tx",
    },
}

# Todas las redes combinadas para consulta de balance
ALL_NETWORKS: dict[str, str] = {
    name: cfg["rpc"] for name, cfg in {**TESTNETS, **MAINNETS}.items()
}

DEFAULT_TESTNET = "Base Sepolia"

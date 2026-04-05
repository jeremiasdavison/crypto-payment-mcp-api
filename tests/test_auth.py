"""
Tests de autenticación — verifica que la API key protege todos los endpoints.
"""


def test_sin_api_key_retorna_401(client):
    """Cualquier endpoint sin key debe rechazar."""
    endpoints = [
        ("GET",  "/balance?address=0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"),
        ("GET",  "/balance/all?address=0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"),
        ("GET",  "/networks"),
        ("GET",  "/price?token=ETH"),
        ("GET",  "/prices?tokens=ETH,BTC"),
    ]
    for method, path in endpoints:
        r = client.request(method, path)
        assert r.status_code == 401, f"{method} {path} debería retornar 401, got {r.status_code}"


def test_api_key_incorrecta_retorna_401(client):
    r = client.get("/networks", headers={"X-API-Key": "clave-falsa"})
    assert r.status_code == 401


def test_api_key_correcta_permite_acceso(client, auth_headers):
    r = client.get("/networks", headers=auth_headers)
    assert r.status_code == 200


def test_health_no_requiere_auth(client):
    """El endpoint raíz es público (para monitoreo)."""
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

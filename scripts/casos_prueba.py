"""Ejecuta la matriz de casos de prueba CP-01..CP-05 en los dos modos de saga.

Sin dependencias externas: solo la librería estándar. Requiere el stack levantado.

    python scripts/casos_prueba.py                 # ambos modos
    python scripts/casos_prueba.py orchestration   # solo orquestación
"""

import json
import sys
import time
import urllib.error
import urllib.request

GATEWAY = "http://localhost:8000"
TIMEOUT_SEGUNDOS = 120
DELAY = 2.0  # el mínimo permitido, para que la verificación no sea eterna


def _request(method: str, path: str, body: dict | None = None, headers: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(f"{GATEWAY}{path}", data=data, method=method)
    request.add_header("Content-Type", "application/json")
    for name, value in (headers or {}).items():
        request.add_header(name, value)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"null")


def get(path: str) -> dict:
    return _request("GET", path)[1]


def balances() -> dict[str, int]:
    return {cuenta["id"]: cuenta["balance_cents"] for cuenta in get("/api/accounts")}


def money(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def esperar_estado_final(transfer_id: str) -> dict:
    limite = time.monotonic() + TIMEOUT_SEGUNDOS
    while time.monotonic() < limite:
        transfer = get(f"/api/transfers/{transfer_id}")
        if transfer["status"] not in ("PENDIENTE", "EN_PROCESO", "COMPENSANDO"):
            time.sleep(1)  # deja que llegue la telemetría rezagada del último paso
            return get(f"/api/transfers/{transfer_id}")
        time.sleep(1)
    raise TimeoutError(f"La transferencia {transfer_id} no alcanzó un estado final")


CASOS = [
    {
        "id": "CP-01",
        "nombre": "Camino feliz",
        "origen": "ACC-001", "destino": "ACC-002", "monto": 100_000,
        "caos": {},
        "estado": "CONFIRMADO",
        "compensaciones_esperadas": 0,
    },
    {
        "id": "CP-02",
        "nombre": "Fondos insuficientes",
        "origen": "ACC-003", "destino": "ACC-001", "monto": 80_000,
        "caos": {},
        "estado": "RECHAZADO_FONDOS",
        "compensaciones_esperadas": 0,
    },
    {
        "id": "CP-03",
        "nombre": "Fraude detectado",
        "origen": "ACC-001", "destino": "ACC-002", "monto": 100_000,
        "caos": {"force_fraud": True},
        "estado": "RECHAZADO_RIESGO",
        "compensaciones_esperadas": 1,
    },
    {
        "id": "CP-04",
        "nombre": "Caída de la red interbancaria",
        "origen": "ACC-001", "destino": "ACC-002", "monto": 100_000,
        "caos": {"clearing_timeout": True},
        "estado": "RECHAZADO_RED",
        "compensaciones_esperadas": 2,
    },
]


def crear_transferencia(caso: dict, modo: str, key: str) -> tuple[int, dict]:
    caos = {"force_fraud": False, "clearing_timeout": False, **caso["caos"]}
    return _request(
        "POST", "/api/transfers",
        {
            "source_account": caso["origen"],
            "destination_account": caso["destino"],
            "amount": caso["monto"],
            "mode": modo,
            "chaos": caos,
            "delay_seconds": DELAY,
        },
        {"Idempotency-Key": key},
    )


def verificar(caso: dict, modo: str) -> list[str]:
    """Devuelve la lista de fallos encontrados (vacía si el caso pasa)."""
    fallos = []
    antes = balances()
    key = _request("POST", "/api/idempotency-keys")[1]["idempotency_key"]

    status_http, _ = crear_transferencia(caso, modo, key)
    if status_http != 202:
        fallos.append(f"se esperaba HTTP 202 al crear, llegó {status_http}")

    transfer = esperar_estado_final(key)
    despues = balances()
    monto_cents = caso["monto"] * 100

    if transfer["status"] != caso["estado"]:
        fallos.append(f"estado {transfer['status']}, se esperaba {caso['estado']}")

    # Saldos: solo el camino feliz mueve dinero.
    if caso["estado"] == "CONFIRMADO":
        esperado = dict(antes)
        esperado[caso["origen"]] -= monto_cents
        esperado[caso["destino"]] += monto_cents
    else:
        esperado = antes
    for cuenta, saldo in esperado.items():
        if despues[cuenta] != saldo:
            fallos.append(f"saldo de {cuenta}: {money(despues[cuenta])}, se esperaba {money(saldo)}")

    if sum(antes.values()) != sum(despues.values()):
        fallos.append("el dinero total del sistema cambió")

    compensados = [p for p in transfer["steps"] if p["status"] == "COMPENSATED"]
    if len(compensados) != caso["compensaciones_esperadas"]:
        fallos.append(f"{len(compensados)} compensaciones, se esperaban {caso['compensaciones_esperadas']}")

    # Orden inverso estricto: las compensaciones ocurren al revés del orden de ida.
    orden_ida = ["DEBIT", "RISK", "CLEARING", "CREDIT"]
    marcas = [(p["updated_at"], p["step"]) for p in compensados]
    secuencia = [paso for _, paso in sorted(marcas)]
    esperada = sorted((p["step"] for p in compensados), key=lambda s: -orden_ida.index(s))
    if secuencia != esperada:
        fallos.append(f"compensaciones en orden {secuencia}, se esperaba {esperada}")

    # CP-05: reenviar la misma Idempotency-Key no debe cobrar dos veces.
    status_http, repetida = crear_transferencia(caso, modo, key)
    if status_http != 200 or not repetida["duplicate"]:
        fallos.append(f"CP-05: el reintento respondió {status_http} duplicate={repetida.get('duplicate')}")
    if balances() != despues:
        fallos.append("CP-05: el reintento movió saldos")

    return fallos


def main() -> int:
    modos = sys.argv[1:] or ["orchestration", "choreography"]
    etiquetas = {"orchestration": "ORQUESTACIÓN", "choreography": "COREOGRAFÍA"}
    total_fallos = 0

    for modo in modos:
        print(f"\n=== {etiquetas.get(modo, modo)} ===")
        estado, _ = _request("POST", "/api/admin/reset")
        if estado != 200:
            print(f"  no se pudo reiniciar el estado (HTTP {estado})")
            return 1
        inicial = sum(balances().values())

        for caso in CASOS:
            inicio = time.monotonic()
            fallos = verificar(caso, modo)
            marca = "OK  " if not fallos else "FALLA"
            print(f"  {marca} {caso['id']} {caso['nombre']:<34} {time.monotonic() - inicio:5.1f}s")
            for fallo in fallos:
                print(f"        - {fallo}")
            total_fallos += len(fallos)

        final = sum(balances().values())
        if inicial != final:
            print(f"  FALLA invariante: el dinero total pasó de {money(inicial)} a {money(final)}")
            total_fallos += 1
        else:
            print(f"  OK   dinero total invariante: {money(final)}")

    print("\nTodos los casos pasaron." if not total_fallos else f"\n{total_fallos} verificaciones fallaron.")
    return 0 if not total_fallos else 1


if __name__ == "__main__":
    raise SystemExit(main())

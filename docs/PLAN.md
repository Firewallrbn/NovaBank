# Plan de arquitectura — NovaBank Saga

Documento de diseño del taller (ver `TALLER.md`). Resume las decisiones de arquitectura, contratos entre servicios y el orden de implementación.

## Contexto

Construir desde cero las capas obligatorias del taller: frontend con simulador de caos, API Gateway con idempotencia, tres microservicios bancarios con datos aislados, lógica Saga en **ambas** modalidades (orquestación y coreografía) y observabilidad con delays de 2–4 s. El 40 % de la nota es compensación estricta en orden inverso sin dinero perdido ni estados en limbo, así que el diseño prioriza eso.

**Stack:** Python 3.12 + FastAPI · RabbitMQ (coreografía) · React + Vite (TS) · SQLite por servicio · Prefect 3 como motor de observabilidad · `docker compose up` · código en inglés, UI/docs y nombres de estados/eventos en español (como en el enunciado).

## Arquitectura

```
Frontend (React, nginx :5173) --/api--> API Gateway (:8000, gateway.db)
                                          ├─ mode=orchestration → HTTP → Orchestrator (:8001, orchestrator.db, flow Prefect)
                                          │                                  └─ HTTP comandos → Account / Risk / Clearing
                                          └─ mode=choreography → publica TransferenciaSolicitada en RabbitMQ
Account (:8101, account.db) · Risk (:8102, risk.db) · Clearing (:8103, clearing.db)
RabbitMQ (:5672, UI :15672) · Prefect server (:4200)
```

- Cada servicio tiene su propio archivo SQLite en **su propio volumen Docker**; ningún servicio accede al volumen de otro (Database-per-Service).
- Ambas modalidades conviven: cada transferencia lleva `mode` y el frontend tiene un toggle Orquestación | Coreografía.
- Dinero siempre en enteros (centavos), nunca `float`.
- `transfer_id` = `Idempotency-Key` (UUID emitido por el Gateway), así la idempotencia se propaga de punta a punta.

## Pasos de la Saga (orden fijado por el enunciado)

| # | Paso | Servicio | Compensación |
|---|---|---|---|
| 1 | Débito en cuenta origen | Account | `refund_debit` (reintegro) |
| 2 | Aprobación de riesgo (reserva cupo diario) | Risk | `revert_risk_approval` (anula y libera cupo) |
| 3 | Liquidación interbancaria — **transacción pivote** | Clearing | `cancel_settlement` solo si el resultado es ambiguo (timeout de transporte) |
| 4 | Crédito en cuenta destino — paso **reintentable** | Account | no se compensa: tras el pivote se reintenta hasta completar |

| Caso | Falla en | Compensaciones (orden inverso) | Estado final |
|---|---|---|---|
| CP-01 | — | — | `CONFIRMADO` |
| CP-02 | paso 1 (UPDATE atómico `WHERE balance >= amount`) | ninguna | `RECHAZADO_FONDOS` |
| CP-03 | paso 2 (switch `force_fraud` o regla real de límites) | refund_debit | `RECHAZADO_RIESGO` |
| CP-04 | paso 3 (switch `clearing_timeout`: la red externa no responde) | revert_risk_approval → refund_debit | `RECHAZADO_RED` |
| CP-05 | reenvío del mismo `Idempotency-Key` | ninguna; se devuelve la transferencia original con `duplicate: true` | saldos inalterados |

Estados adicionales: `RECHAZADO_CUENTA` (cuenta inexistente) y `FALLO_TECNICO` (servicio caído / recuperación hacia atrás).

Estados de paso: `PENDING, RUNNING, SUCCEEDED, FAILED, COMPENSATING, COMPENSATED, SKIPPED` (UI: pendiente / en ejecución / exitoso / fallido / compensando / compensado / omitido).

## Garantías de consistencia

- **Idempotencia en dos niveles:** Gateway (key única + hash del payload; mismo key con payload distinto → 422) y cada servicio (clave `(transfer_id, operación)`; repetir devuelve el resultado previo). Las compensaciones también son idempotentes.
- **Tombstones:** si una compensación llega antes que la operación original (p. ej. tras un timeout), se registra una marca que impide ejecutar después la operación original.
- **Orquestación:** saga log con *write-ahead* (el paso se marca `RUNNING` antes de llamar al servicio). Compensaciones con reintentos. Un bucle de recuperación retoma sagas huérfanas: si el pivote ya se liquidó → recuperación **hacia adelante** (acreditar); si no → **hacia atrás** (compensar).
- **Coreografía:** *transactional outbox* (cambio local + evento en la misma transacción SQLite; un relay publica a RabbitMQ) + *idempotent consumer* (tabla `processed_events`), ack manual y requeue ante fallos transitorios.

## Saga Orquestada (Prefect)

- `services/orchestrator/app/flows.py`: flow `transfer-saga-orquestada` con tasks `debit_source`, `evaluate_risk`, `settle_clearing`, `credit_destination` y tasks de compensación. Cada paso exitoso apila su compensación; ante un fallo se desapila en orden inverso.
- Cada task hace una pausa de `delay_seconds` (2–4 s, configurable desde la UI) antes de actuar.
- En Prefect UI: el paso que falla queda **Failed**; las compensaciones terminan `Completed(name="Compensated")`; el flow termina `Completed(name="CONFIRMADO")` o `Failed(name="RECHAZADO_*")`.

## Saga Coreografiada (RabbitMQ, sin coordinador)

Exchange topic `novabank.events`. Contratos Pydantic compartidos en `libs/saga_common/saga_common/contracts.py`: los servicios dependen solo de los contratos de eventos, nunca de la API de otro servicio. Cada evento transporta el payload completo de la transferencia (*event-carried state transfer*).

| Servicio | Escucha | Emite |
|---|---|---|
| Account | `TransferenciaSolicitada` | `SaldoDebitado` / `DebitoRechazado` |
| Risk | `SaldoDebitado` | `RiesgoAprobado` / `RiesgoRechazado` |
| Clearing | `RiesgoAprobado` | `LiquidacionConfirmada` / `TransferenciaFallida` |
| Account | `LiquidacionConfirmada` | `SaldoAcreditado` |
| Risk (compensación) | `TransferenciaFallida` | `AprobacionRiesgoAnulada` |
| Account (compensación) | `RiesgoRechazado`, `AprobacionRiesgoAnulada` | `DebitoReversado` (con el motivo original) |

- El orden inverso estricto se garantiza por encadenamiento: Account solo reintegra después de que Risk anula su aprobación.
- **Observabilidad con Prefect:** cada handler envuelve su transacción local en un flow propio del servicio (p. ej. `account-on-transferencia-solicitada`) con tags `transfer:<id>` y `choreography`. En Prefect UI se ve el contraste: orquestación = 1 flow con grafo de tasks; coreografía = N flow runs independientes de N servicios, correlacionados por tag.
- El Gateway mantiene una **proyección pasiva** (solo lee eventos, nunca emite comandos) para conocer el estado final.
- La lógica de negocio de cada servicio vive en `domain.py` y la usan tanto el router HTTP (orquestación) como los handlers de eventos (coreografía): lo único que cambia es la coordinación.

## Tiempo real y auditoría

- `saga_common/telemetry.py` publica cada cambio de estado de paso/saga a `novabank.telemetry` (incluye `RUNNING`, que los eventos de dominio no reflejan).
- El Gateway consume telemetría + eventos, los guarda en `audit_log` (bitácora de auditoría) y los empuja al frontend por **SSE** (`GET /api/stream`).

## API Gateway

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/api/idempotency-keys` | Emite un UUID de idempotencia |
| POST | `/api/transfers` | Header `Idempotency-Key`; body: origen, destino, monto, `mode`, `chaos {force_fraud, clearing_timeout}`, `delay_seconds` |
| GET | `/api/transfers` · `/api/transfers/{id}` | Historial / detalle con pasos y auditoría |
| GET | `/api/stream` | SSE con actualizaciones en tiempo real (`?transfer_id=` opcional) |
| GET | `/api/accounts` · `/api/accounts/{id}/ledger` | Saldos y libro mayor (proxy a Account) |
| POST | `/api/admin/reset` | Reinicia datos semilla en todos los servicios |
| GET | `/api/config` | URLs de Prefect UI y RabbitMQ UI para el frontend |

## Estructura del repo

```
docker-compose.yml   .env.example   README.md
libs/saga_common/          contracts, messaging (aio-pika), outbox, inbox, telemetry, db
services/api-gateway/      app/{main,config,db,routes,projection,stream}.py
services/orchestrator/     app/{main,config,db,clients,tracker,flows,recovery}.py
services/account-service/  app/{main,config,db,domain,api,handlers}.py
services/risk-service/     (misma forma; reglas: máximo por transacción, límite diario, force_fraud)
services/clearing-service/ (misma forma; red externa simulada con timeout)
frontend/                  Vite + React + TS → nginx
docs/                      PLAN.md, orquestacion-vs-coreografia.md
```

Cuentas semilla: `ACC-001` (1.000.000,00), `ACC-002` (500.000,00), `ACC-003` (50.000,00 para CP-02), `ACC-004` (250.000,00).

## Orden de implementación

1. Scaffolding: `docker-compose.yml`, `saga_common`, Prefect + RabbitMQ.
2. Account + Orchestrator + Gateway → CP-01 orquestado.
3. Risk + Clearing + compensaciones + idempotencia → CP-02…CP-05 orquestado.
4. Coreografía: outbox/inbox, handlers, flows por servicio, proyección en Gateway.
5. Telemetría + SSE → frontend.
6. README + documento comparativo.

## Verificación

1. `docker compose up --build`; comprobar `localhost:5173`, `localhost:4200`, `localhost:15672` y `/health` de cada servicio.
2. Para cada modo ejecutar CP-01…CP-04 y verificar: pasos con delays visibles, compensaciones en orden inverso, estado final correcto, suma total de dinero invariante y cuenta origen intacta en fallos.
3. CP-05: reenviar la misma operación → `duplicate: true`, un solo cobro.
4. Prefect UI: orquestación = un flow con tasks Failed/Compensated; coreografía = flows independientes filtrables por tag `transfer:<id>`.
5. Robustez: reiniciar el orquestador a mitad de una saga (se recupera) y detener un servicio durante la coreografía (los mensajes se procesan al volver, sin duplicados).

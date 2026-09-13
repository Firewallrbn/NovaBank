# Orquestación vs. Coreografía en NovaBank

Documento comparativo del taller (entregable 2). Las dos modalidades del patrón Saga están implementadas
sobre **exactamente la misma lógica de negocio**: cada servicio expone sus transacciones locales en
`app/domain.py` y lo único que cambia entre modos es **quién decide el siguiente paso**.

| | Orquestación | Coreografía |
|---|---|---|
| Quién coordina | `services/orchestrator` (flow de Prefect) | nadie: cada servicio reacciona a eventos |
| Transporte | HTTP (comandos) | RabbitMQ, exchange topic `novabank.events` |
| Conocimiento del flujo | centralizado en `flows.py` | repartido en las tablas `Reaction` de cada servicio |
| Acoplamiento | el orquestador conoce las 3 APIs; los servicios no se conocen entre sí | nadie conoce APIs ajenas, solo contratos de eventos |
| Orden inverso de compensación | explícito: pila de pasos completados que se desapila | emergente: encadenamiento `TransferenciaFallida → AprobacionRiesgoAnulada → DebitoReversado` |
| Estado de la saga | una fila en `orchestrator.db` (saga log) | no existe estado global; el Gateway lo *proyecta* leyendo eventos |
| Recuperación tras caída | bucle de recuperación que retoma sagas huérfanas | la cola de RabbitMQ retiene el mensaje; el servicio lo procesa al volver |
| Trazabilidad en Prefect | **1 flow run** con grafo de tasks | **N flow runs** independientes, correlacionados por tag `transfer:<id>` |

## 1. Saga Orquestada

Archivo clave: `services/orchestrator/app/flows.py`.

```
Gateway --POST /sagas--> Orchestrator
                            │ (Prefect flow "transfer-saga-orquestada")
                            ├─1─> POST account-service /accounts/debits
                            ├─2─> POST risk-service    /risk/evaluations
                            ├─3─> POST clearing-service/clearing/settlements   ← pivote
                            └─4─> POST account-service /accounts/credits
```

El flujo vive en un solo lugar y se lee de arriba abajo:

```python
for step, forward in STEPS_BEFORE_PIVOT:      # DEBIT → RISK → CLEARING
    await forward(transfer)
    completed.append(step)                    # pila de compensaciones pendientes
...
except StepRejected as exc:
    return await _rollback(transfer, completed, exc.result.reason, str(exc))
```

Y la marcha atrás es literalmente un recorrido inverso de esa pila:

```python
for step in reversed(to_compensate):
    await COMPENSATIONS[step](transfer)
```

**Garantías propias de este modo**

- *Write-ahead log*: el paso se marca `RUNNING` en `orchestrator.db` **antes** de enviar el comando, así
  que tras un reinicio la recuperación sabe que ese paso pudo haberse ejecutado y lo compensa igual.
- *Transacción pivote*: `CLEARING` es el punto de no retorno. Antes del pivote solo hay recuperación hacia
  atrás; después, solo hacia adelante — `credit_destination` reintenta hasta 10 veces en lugar de compensar.
- *Timeout ambiguo*: si el clearing no responde no se sabe si liquidó. El orquestador trata el paso como
  ejecutado (`exc.ambiguous`) y llama a `cancel_settlement`, que es idempotente y no hace nada si no hubo
  liquidación. Nunca se pierde dinero por asumir de más.

**Fortalezas:** el flujo es evidente, depurable y el orden inverso es imposible de equivocar. Un solo flow
run en Prefect muestra el paso `Failed` y las compensaciones `Completed(name="Compensated")`.

**Debilidades:** el orquestador es un punto único de conocimiento (y de fallo: por eso existe
`recovery_loop`), y añadir un paso obliga a tocar el coordinador.

## 2. Saga Coreografiada

Archivos clave: `libs/saga_common/saga_common/choreography.py` y el `handlers.py` de cada servicio.

```
Gateway --TransferenciaSolicitada--> [bus]
   Account   escucha TransferenciaSolicitada   → SaldoDebitado | DebitoRechazado
   Risk      escucha SaldoDebitado             → RiesgoAprobado | RiesgoRechazado
   Clearing  escucha RiesgoAprobado            → LiquidacionConfirmada | TransferenciaFallida
   Account   escucha LiquidacionConfirmada     → SaldoAcreditado
   ── compensaciones ──
   Risk      escucha TransferenciaFallida      → AprobacionRiesgoAnulada
   Account   escucha RiesgoRechazado
             y AprobacionRiesgoAnulada         → DebitoReversado
```

Ningún servicio importa el cliente HTTP de otro: solo dependen de `contracts.py`. El Gateway no es un
coordinador disfrazado — su `Projection` **solo lee** eventos para pintar la UI, nunca emite comandos.

**Cómo se garantiza el orden inverso sin coordinador.** Es la pregunta difícil de la coreografía, y aquí
se resuelve por **encadenamiento causal**: Account no reintegra el débito al ver `TransferenciaFallida`,
sino al ver `AprobacionRiesgoAnulada`, que solo Risk puede emitir **después** de deshacer su propia
aprobación. La secuencia física es, por construcción, la inversa de la de ida.

**Garantías propias de este modo**

- *Transactional outbox*: el cambio de saldo y el evento saliente se escriben en la **misma transacción
  SQLite** (`enqueue_event` dentro del `with db.transaction()`). Un relay los publica después. Es imposible
  debitar sin publicar el evento, o publicar un evento cuyo débito se perdió.
- *Idempotent consumer*: `inbox.claim` inserta el `event_id` en la misma transacción. Si RabbitMQ reentrega
  el mensaje, la transacción local no se repite.
- *Ack manual*: si la transacción local falla, el mensaje vuelve a la cola y se reintenta. Un servicio caído
  no pierde trabajo; lo procesa al arrancar.

**Fortalezas:** acoplamiento mínimo y resiliencia natural — apagar un servicio a mitad de una saga no la
rompe, solo la pausa.

**Debilidades:** no hay un sitio donde leer "el flujo"; hay que reconstruirlo leyendo las reacciones de los
tres servicios. Por eso la observabilidad deja de ser un lujo y pasa a ser obligatoria.

## 3. Observabilidad: el contraste se ve en Prefect

Ambos modos publican telemetría al exchange `novabank.telemetry`, que el Gateway convierte en bitácora de
auditoría y empuja al frontend por SSE. Cada paso hace una pausa de `delay_seconds` (2–4 s, configurable
desde la UI) **antes** de actuar, para que la marcha atrás se aprecie a simple vista.

En Prefect UI la diferencia es visual e inmediata:

- **Orquestación** → un flow run `transfer-<id>` con su grafo de tasks. Se ve el paso que falló y las
  compensaciones que siguieron.
- **Coreografía** → varios flow runs sueltos (`account-service.TransferenciaSolicitada`,
  `risk-service.SaldoDebitado`, …). Filtrando por el tag `transfer:<id>` aparece la cadena completa: la
  misma saga, pero *sin un dueño*.

Esa captura de pantalla es, literalmente, la diferencia entre los dos patrones.

## 4. Resultado en los casos de prueba

Los cinco casos (`CP-01`…`CP-05`) dan **el mismo estado final y los mismos saldos** en ambos modos; lo que
cambia es el camino. Ejemplo con CP-04 (timeout de la red interbancaria):

| | Orquestación | Coreografía |
|---|---|---|
| Detección | el orquestador recibe el timeout HTTP | Clearing emite `TransferenciaFallida` |
| Compensación 1 | orquestador llama `POST /risk/evaluations/{id}/revert` | Risk reacciona solo y emite `AprobacionRiesgoAnulada` |
| Compensación 2 | orquestador llama `POST /accounts/debits/{id}/refund` | Account reacciona a ese evento y emite `DebitoReversado` |
| Estado final | `RECHAZADO_RED` | `RECHAZADO_RED` |
| Saldos | íntegros | íntegros |

## 5. Cuándo usar cada uno

- **Orquestación** cuando el proceso de negocio es largo, tiene reglas de decisión propias y necesita ser
  auditado o modificado como una unidad. Una transferencia de alto valor con obligaciones regulatorias cae
  aquí: conviene que exista un sitio donde alguien pueda leer el flujo completo.
- **Coreografía** cuando los pasos son reacciones naturales de dominios autónomos y se prioriza la
  disponibilidad y la evolución independiente de los equipos. Escala mejor en organización, peor en
  comprensión.

En producción lo habitual es mezclarlos: orquestar el núcleo transaccional (el dinero) y coreografiar los
efectos secundarios (notificaciones, extractos, analítica). NovaBank implementa ambos para poder
contrastarlos con la misma lógica de negocio y los mismos casos de prueba.

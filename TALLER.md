# Taller Práctico: Implementación del Patrón Saga Bancario

**Coreografía vs. Orquestación y Observabilidad**

- **Módulo:** Arquitectura de Software Distribuida & Sistemas Transaccionales
- **Plazo de Entrega:** 7 días calendario
- **Libertad de Stack Tecnológico:** 100% abierta

## Modalidad

| Aspecto | Detalle |
|---|---|
| Equipos | 2 personas (máximo 3) |
| Dedicación en Aula | 3 horas (laboratorio guiado) |
| Dedicación Autónoma | 7 días (finalización y pruebas) |
| Políticas de Stack | 100% Abierto: los estudiantes son libres de elegir cualquier lenguaje y framework para Frontend, Backend y Bases de Datos |

## 1. Contexto del Negocio y Planteamiento del Problema

Ustedes han sido designados como el equipo líder de arquitectura e ingeniería del banco privado **"NovaBank International"**. La entidad procesa transferencias interbancarias de alto valor y requiere abandonar los bloqueos globales de bases de datos tradicionales (como Two-Phase Commit / 2PC) para garantizar alta disponibilidad y tolerancia a fallos.

El núcleo de la solución radica en adoptar el **Patrón Saga** bajo el modelo **BASE** (Basically Available, Soft state, Eventual consistency). El objetivo prioritario de este taller no es el dominio de una librería específica, sino la correcta implementación de transacciones distribuidas, manejo riguroso de fallos, consistencia eventual y ejecución estricta de transacciones de compensación en reversa.

## 2. Criterios Mínimos de Aceptación: Las 4 Capas Obligatorias

Para que la práctica sea admisible a evaluación, cada equipo debe construir y desplegar las siguientes cuatro capas arquitectónicas, con total autonomía para elegir las tecnologías que prefieran:

### Capa de Frontend (Interfaz de Usuario & Simulador de Caos)

Debe permitir:
- Ingresar los datos de una transferencia bancaria (cuenta origen, destino, importe)
- Activar botones o switches para simular condiciones de error
- Visualizar en tiempo real el avance paso a paso de la transacción y sus compensaciones

*Libertad tecnológica: React, Next.js, Vue, Angular, Svelte, Vanilla HTML/JS, etc.*

### Capa de Backend / API Gateway

Punto de entrada centralizado para:
- Recibir las peticiones del frontend
- Emitir identificadores de idempotencia (UUID)
- Despachar la ejecución hacia la arquitectura de servicios bancarios

*Libertad tecnológica: Node.js/Express/Nest, Python/FastAPI/Django, Java/Spring Boot, C#/.NET, Go, Rust, etc.*

### Capa de Microservicios de Dominio Bancario

Mínimo tres servicios independientes con almacenamiento propio y desacoplado (Database-per-Service o esquemas lógicamente aislados):

1. **Servicio de Cuentas y Saldos (Account & Ledger):** débitos, créditos y reversas de balance.
2. **Servicio de Riesgo y Prevención de Fraude:** reglas de validación operativa y límites diarios.
3. **Pasarela Interbancaria (Clearing Gateway):** simulación de liquidación externa de fondos.

### Capa Lógica de Implementación del Patrón Saga

**El núcleo evaluativo del taller.** Mecanismo capaz de coordinar la secuencia de transacciones locales y, ante un error en cualquier fase intermedia, disparar las transacciones de compensación en orden inverso para restituir el estado de las cuentas. Debe evidenciarse tanto en **Orquestación** como en **Coreografía**.

### Capa de Observabilidad (Seguimiento de Tareas y Delays)

Integración con un motor de flujos (como Prefect o equivalente de orquestación) o un dashboard de trazabilidad que permita pausar intencionalmente cada micro-paso (delays configurables de 2 a 4 segundos) para apreciar visualmente los estados: **en ejecución**, **fallido** y **compensado**.

## 3. Núcleo Arquitectónico: Orquestación vs. Coreografía

Los estudiantes deben implementar y contrastar activamente las dos modalidades del patrón Saga:

- **Saga Orquestada:** Un orquestador central (coordinador o flujo de Prefect) comanda directamente a cada servicio qué acción ejecutar. Si ocurre un fallo, el orquestador captura el error y llama explícitamente a los endpoints o métodos de compensación de los servicios que ya habían tenido éxito previo.

- **Saga Coreografiada:** No existe un coordinador central. Los servicios emiten eventos de dominio en un bus o canal de mensajería (ej. `TransferenciaSolicitada`, `SaldoDebitado`, `RiesgoAprobado`). Si la pasarela interbancaria falla, emite un evento de error (ej. `TransferenciaFallida`), y los demás servicios reaccionan de manera autónoma ejecutando sus compensaciones locales.

## 4. Matriz de Casos de Prueba y Simulación de Fallos

El frontend y backend deben permitir reproducir con facilidad los siguientes escenarios obligatorios:

| ID Caso | Escenario | Simulación / Disparador | Acción de Compensación | Consistencia Final |
|---|---|---|---|---|
| **CP-01** | Camino Feliz (Éxito Total) | Transferencia normal sin errores. | Ninguna (no hay errores). | Saldo debitado en origen y acreditado en destino. Estado: `CONFIRMADO`. |
| **CP-02** | Fallo Inicial (Fondos Insuficientes) | Monto mayor al saldo disponible. | Rechazo inmediato sin llamadas de reversa. | Cuentas bancarias intactas. Estado: `RECHAZADO_FONDOS`. |
| **CP-03** | Fallo Intermedio (Riesgo / Antifraude) | Switch en frontend para forzar fraude. | Se reembolsa el débito contable hecho en el paso 1. | Saldo reintegrado al 100% en la cuenta origen. Estado: `RECHAZADO_RIESGO`. |
| **CP-04** | Fallo Terminal (Caída de Red Externa) | Switch para timeout en pasarela interbancaria. | Se anula aprobación de riesgo y se reintegra el débito contable. | Saldos íntegros y bitácora de auditoría registrada. Estado: `RECHAZADO_RED`. |
| **CP-05** | Idempotencia ante Reintentos | Reenvío del mismo identificador de operación. | Reconocimiento de duplicado sin ejecutar dobles cobros. | Saldos inalterados ante reintentos. |

## 5. Dinámica de Trabajo y Entregables

- **Sesión Presencial (3 horas):** Modelado del flujo de estados de la Saga, definición de contratos entre servicios y puesta en marcha del orquestador inicial con el primer caso exitoso (CP-01).
- **Trabajo Autónomo (7 días calendario):** Conexión del frontend, implementación de la compensación completa, contraste entre orquestación y coreografía, y pruebas de consistencia.

### Entregables

1. Repositorio Git con código ejecutable e instrucciones claras de despliegue.
2. Breve documento explicativo comparando orquestación frente a coreografía.
3. Video demostrativo funcional (máximo 6 minutos) exhibiendo los fallos y compensaciones.

## 6. Rúbrica de Calificación Oficial (Escala de 0.0 a 5.0)

La evaluación concentra su mayor peso en la correcta aplicación del Patrón Saga y la consistencia eventual. La nota final se calcula sumando la puntuación ponderada de cada criterio hasta un máximo de **5.0 / 5.0**:

### 1. Lógica de Patrón Saga y Compensaciones (Foco Principal) — 40% (2.0 puntos)

| Nivel | Descripción |
|---|---|
| Sobresaliente (4.5 - 5.0) | Manejo estricto de transacciones compensatorias en orden inverso. Consistencia eventual garantizada sin dinero perdido ni estados en limbo en todos los casos de prueba. |
| Aceptable (3.0 - 4.4) | La compensación funciona en la mayoría de escenarios pero omite pasos en fallos tardíos o carece de control estricto de reversa. |
| Insuficiente (0.0 - 2.9) | No hay transacciones de compensación reales; ante un fallo el dinero queda debitado o los datos quedan en estado inconsistente. |

### 2. Comparativa: Orquestación vs. Coreografía — 20% (1.0 punto)

| Nivel | Descripción |
|---|---|
| Sobresaliente (4.5 - 5.0) | Se implementan y demuestran ambos enfoques con claridad técnica, evidenciando las diferencias en acoplamiento y control de flujo. |
| Aceptable (3.0 - 4.4) | Ambos enfoques están presentes, pero la coreografía tiene dependencias circulares o acoplamiento innecesario. |
| Insuficiente (0.0 - 2.9) | Solo se implementa una de las dos modalidades o no hay distinción conceptual en el código. |

### 3. Observabilidad, Delays y Trazabilidad de Estados — 15% (0.75 puntos)

| Nivel | Descripción |
|---|---|
| Sobresaliente (4.5 - 5.0) | Uso claro de delays para visualizar la evolución del flujo (Prefect o dashboard de trazabilidad), con registro de auditoría de cada cambio de estado. |
| Aceptable (3.0 - 4.4) | Existe observabilidad pero los delays no permiten apreciar la marcha atrás o los registros de estado son ambiguos. |
| Insuficiente (0.0 - 2.9) | Flujo de caja negra: no se aprecian los estados intermedios ni se ofrece trazabilidad durante los fallos. |

### 4. Frontend & Simulador Interactivo de Caos — 10% (0.50 puntos)

| Nivel | Descripción |
|---|---|
| Sobresaliente (4.5 - 5.0) | Interfaz funcional y clara con switches para inducir cada caso de fallo, mostrando visualmente el progreso en tiempo real de cada paso. |
| Aceptable (3.0 - 4.4) | Frontend funcional pero básico; permite simular fallos pero carece de visualización reactiva paso a paso. |
| Insuficiente (0.0 - 2.9) | No hay interfaz de usuario o no permite interactuar con los casos de error simulados. |

### 5. Microservicios y Aislamiento de Datos — 10% (0.50 puntos)

| Nivel | Descripción |
|---|---|
| Sobresaliente (4.5 - 5.0) | Separación de dominios con datos aislados por servicio; soporte de idempotencia básica para prevenir dobles cobros ante reintentos. |
| Aceptable (3.0 - 4.4) | Los servicios están divididos pero comparten estructuras de datos directas o no contemplan idempotencia. |
| Insuficiente (0.0 - 2.9) | Monolito con acceso directo a una misma base de datos sin aislamiento de dominios. |

### 6. Documentación, Video y Despliegue — 5% (0.25 puntos)

| Nivel | Descripción |
|---|---|
| Sobresaliente (4.5 - 5.0) | Instrucciones claras de ejecución, video explicativo conciso de alta calidad técnica y diagramas de flujo completos. |
| Aceptable (3.0 - 4.4) | Documentación o video incompletos, o pasos de ejecución con dependencias manuales no documentadas. |
| Insuficiente (0.0 - 2.9) | Ausencia de video demostrativo o proyecto no ejecutable. |

**TOTAL GENERAL: 100% — 5.0 Puntos**

*Nota final calculada sobre la escala estándar de 0.0 a 5.0*

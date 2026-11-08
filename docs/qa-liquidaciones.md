# Plan de QA — Liquidaciones (cierre de caja)

Script: `scripts/qa_liquidations_flow.py` (flujo completo, 2 escenarios) y `scripts/qa_liquidations.py` (reglas, permisos, rendimiento).
Se ejecutan dentro del contenedor `api`; no borran nada (rutas y clientes `QD Liq …`).

## Actores
| Rol | Usuario | Hace |
|---|---|---|
| Cobrador (05) | `qd_carlos`, asignado a la ruta | Cobra cuotas, registra gastos y (escenario A) entrega créditos nuevos |
| Admin (03) con la misma ruta | `admin_norte`, asignado a la ruta | Revisa la vista previa, cierra la caja a nombre del cobrador, confirma y reabre |

## Escenario A — con créditos nuevos / Escenario B — sin créditos nuevos
1. **Preparación:** ruta nueva con cobrador y admin asignados; 10 créditos con cuota de hoy, una atrasada, una para abono parcial y una para pago de más.
2. **Cobrador cobra (10 recibos):** cuota de hoy, atrasada cobrada hoy, parcial ($40.000 de $100.000), excedente ($130.000 → $30.000 a favor) y 6 más.
3. **Cobrador registra 2 gastos** ($25.000 y $18.000).
4. **(Solo A)** el cobrador entrega 2 créditos nuevos ($300.000 y $200.000), con su lista.
5. **Admin, vista previa** (a nombre del cobrador y consolidada): cada cifra == cálculo independiente sobre filas crudas (recaudo $1.070.000, gastos $43.000, créditos nuevos, excedente, parciales, meta).
6. **Admin cierra la caja** con un faltante de $5.000 → esperado = base + recaudo − gastos − créditos nuevos; diferencia −$5.000; estado pendiente.
7. **Guardado en lote:** el cierre usa **un solo `UPDATE` por tabla** (pagos y gastos), sin importar cuántos pagos incluya; cada pago y gasto queda con `liquidated=true`, `date_liquidated` (hoy, Colombia), `liquidated_by` (admin) y `liquidation_id`.
8. Los pagos liquidados salen de **Cobro del día**; un segundo cierre del mismo cobrador y día → 409.
9. **Permisos:** el cobrador no puede confirmar (403) ni reabrir (403).
10. **Confirmar:** el admin confirma; el detalle lista recibos, gastos y créditos nuevos sin "desactualizado".
11. **Reabrir:** 2 `UPDATE` en lote; pagos y gastos vuelven a `liquidated=false` con fecha, cierre y responsable vacíos; la vista previa recupera las mismas cifras; se vuelve a cerrar con diferencia 0 y se confirma; el historial muestra el cierre y los totales del filtro.

## Cobertura adicional (`qa_liquidations.py`)
Cobro atrasado entra al cierre del día, cierre por cobrador vs consolidado, doble cierre concurrente, "desactualizado" tras un cobro posterior (no se puede confirmar), permisos por marca / rol / ruta, fecha futura, listados paginados con totales, rendimiento (≤ 12 sentencias en la vista previa, ≤ 18 al cerrar).

## Resultado (última corrida)
- `qa_liquidations_flow.py`: 60/60 (A y B).
- `qa_liquidations.py`: 50/50 · regresión `qa_reports.py` 69/69 · `qa_payment_history.py` 31/31 · `qa_loan_create.py` 87/87.

## Prueba desde la interfaz (UI)
Preparación (una vez):
1. `docker compose exec api python scripts/seed_liquidation_ui.py` → ruta **QD UI Liquidación** con 8 clientes (5 con cuota de hoy, 2 atrasados, 1 para abonar), asignada a `qd_carlos` (cobrador) y `admin_norte` (admin).
2. Cuenta del cobrador en Clerk (la crea quien administra Clerk, no el QA automatizado):
   `docker compose exec api python scripts/sync_users_to_clerk.py --only qd_carlos --password 'KobrosTest123'`
   (`admin_norte` y `super_norte` ya tienen cuenta.)

Recorrido: **cobrador** (Cobro del día → ruta QD UI Liquidación): cobrar cuotas de hoy, una atrasada, un parcial y un pago de más; registrar 2 gastos; (escenario A) crear un crédito nuevo con "Valor pagado hoy". **Admin** (Liquidaciones): elegir ruta y cobrador, revisar cifras, cerrar con un faltante, confirmar, reabrir y volver a cerrar. Comparar cada cifra con la API.

## Resultado de la prueba desde la interfaz (escenario A, con crédito nuevo)
Cobrador `qd_carlos` (UI): 10 cobros en Cobro del día (cuotas de hoy con "Todo", pago de más $130.000, abono parcial $40.000, cobro total con 5 cuotas atrasadas), 2 gastos desde Gastos ($25.000 y $18.000) y un crédito nuevo ($300.000, con $100.000 de "Valor pagado hoy" → saldo a favor +$40.000). Admin (UI): Liquidaciones → ruta + cobrador → recaudo $1.070.000 (11 recibos), gastos $43.000, créditos nuevos −$300.000 (1), esperado $1.227.000; cierre con faltante de $5.000 → confirmar → reabrir. Tras reabrir: 11 pagos y 2 gastos con `liquidated=false` y sin fecha, cierre ni responsable.
Hallazgo corregido: el historial del cliente en el asistente de crédito traía los créditos de TODO el sistema (el listado no filtraba por `client_id` ni por marca/ruta); ahora filtra por cliente y por alcance del usuario.

## QA de alcance por id (`scripts/qa_access.py`, 19/19)
Crédito y pago pedidos por id respetan marca, rol y ruta asignada: otra marca o un cobrador no asignado reciben 404; el cobrador no edita ni elimina créditos (403); cobrar un pago ajeno se rechaza sin mover dinero; listar pagos sin `loan_id` se rechaza (400).

## QA de seguridad (alcance por marca, rol y ruta)

`scripts/qa_security.py` (73 verificaciones) prueba todos los endpoints que reciben un id con:
A) administrador de otra marca, B) cobrador no asignado a la ruta, C) cobrador asignado ejecutando acciones de administración.
Resultado: 73/73. Regresiones: qa_access 19/19, qa_liquidations 50/50, qa_liquidations_flow 60/60, qa_payment_history 31/31, qa_loan_create 90/90, qa_reports 69/69.

Cambios de comportamiento: el cobrador ya no lista usuarios, no activa/desactiva clientes, no crea/edita rutas ni crea/edita/borra pagos manuales;
`GET /payments/` exige `loan_id` y `GET /clientroute/` exige `route_id`; Cartera/mora excluyen rutas inactivas (igual que el dashboard).

## Job diario de mora (sin worker)

`app/infrastructure/utils/default_scheduler.py` corre desde el `lifespan` del API: al arrancar y todos los días 00:05 (Bogotá). Pasa a `mora` las cuotas `pendiente` con `pay_date < hoy` sin cobrar (créditos y rutas activos) y suma su faltante a `loans.total_default`. Idempotente, con advisory lock. Se apaga con `MORA_JOB_ENABLED=false`. Manual/cron externo: `python scripts/mark_overdue_payments.py [--dry-run]`. QA: `scripts/qa_mora_job.py` (13/13).

# Consistencia y errores entre dominios

| Operacion | Gestores | Consistencia | Posible fallo | Conducta | Recuperacion / reintento |
|---|---|---|---|---|---|
| Crear envio | PostgreSQL (envio + evento + outbox) | Fuerte: 1 transaccion | Postgres caido | `5xx`/`503`, no se guarda nada | Reintento seguro: el codigo se genera nuevo (no hay doble registro si no hubo respuesta `201`) |
| Cambiar estado | PostgreSQL | Fuerte; `FOR UPDATE` serializa cambios del mismo envio | Reintento por timeout | Mismo `evento_id` -> `200 repetido`, sin duplicar | Seguro reintentar siempre con el mismo `evento_id` |
| Transicion invalida | PostgreSQL | Fuerte | Cliente enviando estado imposible | `409`; el historial no cambia | No aplica: corregir la peticion |
| Asignar repartidor | PostgreSQL | Fuerte: `FOR UPDATE` sobre repartidor + indice unico parcial | Dos asignaciones simultaneas | Una `201`, otra `409` (sin capacidad) | Reintentar con el mismo `evento_id`; liberar cupo entregando/cancelando/liberando |
| Sincronizar a busqueda | PostgreSQL -> MongoDB (outbox + worker) | **Eventual** | Mongo caido o worker detenido | Registro sigue operando; `/buscar` responde `503`; `/health` = degradado; outbox acumula avisos | El worker reintenta cada ciclo; si se pierde la coleccion: `POST /sincronizacion/reconstruir` |
| Confirmar entrega | MongoDB (evidencia) + PostgreSQL (estado) | **Sin ACID conjunto**; orden fijo: 1) evidencia 2) estado | (a) Mongo caido | `503`, el estado NO cambia (no se entrega sin evidencia) | Reintentar con los mismos `evidencia_id`/`evento_id` |
| | | | (b) Postgres falla tras guardar evidencia | Evidencia huerfana temporal; envio sigue `en_transito` | Reintento idempotente completa el estado sin duplicar la evidencia |
| Posicion del repartidor | Redis (TTL) | Efimera | Redis reiniciado/caido | Posicion `no vigente`; `503` si no responde; el despacho y las entregas siguen | Se repuebla con la siguiente posicion enviada |
| Aceptar / rechazar asignacion | PostgreSQL | Fuerte (`FOR UPDATE` sobre envio y asignacion) | Aceptacion repetida o tardia | Mismo `evento_id` -> `200 repetido`; rechazar tras aceptar -> `409`; retirar sin aceptar -> `409` | Reintento idempotente |
| Incidencia | PostgreSQL | Fuerte | Motivo ausente | `422`; el estado no cambia | Reenviar con `detalle`; el operador la resuelve (reanudar o devolver) |
| Estado vs historial | PostgreSQL | Fuerte | - | `GET /envios/{codigo}` devuelve `consistente` (estado == ultimo evento) | Si hubiera contradiccion, **el historial manda**: el estado se reconstruye desde el ultimo evento |

## Source of Truth
| Dato | Fuente oficial | Derivados |
|---|---|---|
| Estado actual, asignaciones | PostgreSQL | proyeccion en MongoDB |
| Historial de eventos | PostgreSQL (append-only) | - |
| Evidencia de entrega confirmada | MongoDB | - (no es cache; no se reconstruye) |
| Busqueda | (derivado) | MongoDB `envios_busqueda`, reconstruible |
| Posicion / conexion | Redis (efimero, no autoritativo) | - |

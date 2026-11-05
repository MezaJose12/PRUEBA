# Especificacion de la API

La especificacion OpenAPI completa se genera sola: `http://localhost:8000/docs` (interactiva) y
`http://localhost:8000/openapi.json` (`scripts/exportar_openapi.sh` la guarda en `docs/openapi.json`).

Encabezado `X-Rol: cliente|operador|repartidor|administrador` (rol simulado). `cualquiera` = cualquier rol valido; `-` = sin restriccion.

| Metodo y ruta | Rol | Payload (resumen) | Respuestas |
|---|---|---|---|
| `GET /health` | - | - | 200 ok/degradado, 503 Postgres caido |
| `POST /envios` | cualquiera | remitente, destinatario, origen, destino, tipo_servicio (activo), zona_id | 201, 401, 422 |
| `GET /envios?estado=&zona_id=` | - | - | 200 (incluye repartidor y ultimo_detalle) |
| `GET /envios/{codigo}` | - | - | 200 (envio, eventos, asignacion, consistente), 404 |
| `PATCH /envios/{codigo}/estado` | segun estado destino: `cancelado` cliente/operador/admin; `retirado`, `en_transito`, `incidencia`, `devuelto` repartidor/operador/admin; `creado` operador/admin | nuevo_estado, actor, evento_id (UUID), detalle (obligatorio en `incidencia`) | 200 (repetido true/false), 403, 404, 409, 422 |
| `POST /envios/{codigo}/entrega` | repartidor, administrador | receptor, observacion, foto_url, actor, evidencia_id, evento_id | 201, 200 reintento, 403, 404, 409, 422, 503 |
| `GET /envios/{codigo}/evidencia` | - | - | 200, 404, 503 |
| `GET /repartidores` | - | - | 200 (carga_actual, disponible) |
| `GET /repartidores/{id}/tareas` | - | - | 200 (asignacion_id, aceptada) |
| `POST /asignaciones` | operador, administrador | codigo_envio, repartidor_id, actor, evento_id | 201, 200 reintento, 403, 404, 409 (sin capacidad / estado), 422 |
| `PATCH /asignaciones/{id}/aceptar` | repartidor, administrador | actor, evento_id | 200, 403, 404, 409 |
| `PATCH /asignaciones/{id}/rechazar` | repartidor, administrador | actor, evento_id | 200, 403, 404, 409 (ya aceptada) |
| `PATCH /asignaciones/{id}/liberar` | operador, administrador | actor, evento_id | 200, 403, 404, 409 |
| `PUT /repartidores/{id}/posicion` | repartidor, administrador | lat, lon | 200, 403, 404, 422, 503 |
| `GET /repartidores/{id}/posicion` | - | - | 200 (vigente true/false), 503 |
| `GET /posiciones` | - | - | 200, 503 |
| `GET /buscar?codigo=&zona=&estado=&destinatario=&desde=&hasta=` | - | - | 200, 503 (Mongo caido) |
| `GET /sincronizacion/estado` | - | - | 200 |
| `POST /sincronizacion/reconstruir` | operador, administrador | - | 200, 403 |
| `GET /zonas` | - | - | 200 |
| `POST /zonas` / `PATCH /zonas/{id}` | administrador | nombre | 201/200, 403, 404, 409, 422 |
| `GET /tipos-servicio?todos=` | - | - | 200 (solo activos por defecto) |
| `POST /tipos-servicio` / `PATCH /tipos-servicio/{id}` | administrador | nombre, activo | 201/200, 403, 404, 409, 422 |
| `POST /repartidores` / `PATCH /repartidores/{id}` | administrador | nombre, capacidad_max, activo | 201/200, 403, 404, 409, 422 |

Codigos usados: `200` ok / reintento idempotente · `201` creado · `401` falta X-Rol · `403` rol sin permiso · `404` no existe ·
`409` conflicto (transicion invalida, sin capacidad, duplicado, regla de negocio) · `422` validacion · `503` dependencia no disponible.

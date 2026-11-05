# Informe tecnico - Mensajeria urbana (Proyecto B)

> BORRADOR GENERADO COMO PUNTO DE PARTIDA. Antes de entregarlo: lee cada seccion, ajustala a lo que realmente
> ejecutaste, agrega tus capturas en `docs/evidencias/`, los resultados reales de las pruebas y las fuentes
> que consultaste para la matriz de gestores. Debes poder explicar cada decision en la defensa.

## 1. Contexto y alcance
Sistema web para una empresa de mensajeria urbana: los clientes registran envios y los siguen; los operadores
asignan repartidores respetando su capacidad; los repartidores reportan estados y registran evidencia simulada;
el administrador mantiene zonas y repartidores. Todos los datos son ficticios; no hay GPS ni mapas reales.

## 2. Mapa de dominios
| Dominio | Gestor | Motivo breve |
|---|---|---|
| Solicitudes y envios | PostgreSQL | unicidad y transacciones |
| Despacho y asignaciones | PostgreSQL | control de capacidad concurrente |
| Seguimiento y eventos | PostgreSQL (tabla append-only) | orden, auditoria y coherencia con el estado |
| Evidencias de entrega | MongoDB | datos heterogeneos, documento por envio |
| Consulta operativa | MongoDB (proyeccion) | filtros rapidos, reconstruible |
| Estado temporal | Redis | TTL nativo |

## 3-4. Analisis y seleccion de gestores
Ver `matriz_gestores.md` (6 dominios, alternativa descartada y justificacion en cada uno).

## 5. Modelo de datos
**PostgreSQL** (`db/postgres/init.sql`): `zonas`, `tipos_servicio` (administrable), `repartidores(capacidad_max)`, `envios(codigo UNIQUE, estado CHECK)`,
`asignaciones` (indice unico parcial `WHERE activa` = un vinculo activo por envio; `aceptada_en` = aceptacion del repartidor), `eventos_envio` (PK `evento_id` UUID, columna `detalle`,
indice `(envio_id, fecha)`, trigger que impide UPDATE/DELETE/TRUNCATE), `outbox`. Identificador compartido entre gestores: **`codigo`** del envio.

**MongoDB** (`db/mongo/init.js`):
```json
// envios_busqueda (proyeccion)           // evidencias (oficial)
{ "_id": "ENV-9F3A1C7B", "estado": "en_transito",   { "_id": "ENV-9F3A1C7B", "evidencia_id": "uuid",
  "zona": "Norte", "destinatario": "Luis ...",         "receptor": "...", "observacion": "...",
  "creado_en": "...", "actualizado_en": "..." }        "foto_url": "https://...", "actor": "repartidor-1" }
```
Indices: estado, zona, destinatario, creado_en; `evidencia_id` unico. Retencion: sin borrado automatico (laboratorio).

**Redis**: `repartidor:{id}:posicion` -> JSON `{lat, lon, actualizado}` con `EX` = `TTL_POSICION_SEGUNDOS` (60 s).

## 6. Source of Truth
Ver la tabla al final de `tabla_consistencia.md`. Regla clave: PostgreSQL es la fuente del estado y del historial;
si hubiera contradiccion, **el historial (ultimo evento) manda** porque es append-only. La evidencia confirmada es
oficial en MongoDB. La busqueda y Redis nunca son fuente unica de una operacion que requiera confirmacion.

## 7. Arquitectura y flujos
Diagramas en `diagramas/diagramas.md` (arquitectura + 2 flujos end-to-end).

## 8. Transacciones, idempotencia y recuperacion
- **Transaccion local** (PostgreSQL): estado + evento + outbox (+ liberar cupo) en una sola transaccion.
- **Concurrencia**: `SELECT ... FOR UPDATE` sobre el repartidor (capacidad) y sobre el envio (cambios de estado).
- **Idempotencia**: `evento_id` unico por cambio; `evidencia_id` por evidencia; reintento = `200 repetido`.
- **Consistencia eventual**: outbox + worker (`FOR UPDATE SKIP LOCKED`), reintenta si Mongo cae.
- **Sin ACID entre gestores**: la entrega escribe primero la evidencia y luego el estado; el reintento idempotente cubre el fallo intermedio.
- **Recuperacion**: `POST /sincronizacion/reconstruir` regenera la busqueda desde PostgreSQL; Redis se repuebla solo.

## 9. Tabla de consistencia y errores
Ver `tabla_consistencia.md`.

## 10. Pregunta de investigacion: seguimiento como filas, documentos o eventos inmutables
**Consultas dominantes**: (1) linea de tiempo de un envio ordenada por fecha; (2) estado actual; (3) auditoria por actor/fecha.
| Opcion | A favor | En contra |
|---|---|---|
| Filas relacionales (tabla `eventos_envio`) | Misma transaccion que el estado; indice `(envio_id, fecha)` resuelve (1) y (3); SQL para auditoria | Esquema fijo para atributos nuevos del evento |
| Documento por envio con eventos embebidos | Una lectura trae todo el envio | Documento crece sin limite; actualizar estado y evento en gestores distintos rompe la coherencia; auditoria cruzada es incomoda |
| Eventos inmutables (event sourcing puro) | Auditoria perfecta; estado = replay | Mas complejidad operativa; hace falta proyeccion para (2) y consultas; sobredimensionado aqui |
**Decision**: filas **append-only** en PostgreSQL (inmutabilidad garantizada por un trigger que rechaza `UPDATE`/`DELETE`/`TRUNCATE`). Se obtiene la auditabilidad de
los eventos inmutables sin un motor adicional. El estado actual se guarda tambien en `envios` (lectura rapida) y se **verifica**
contra el ultimo evento (`consistente`); si divergieran, se reconstruye desde el historial. Costo operativo: un solo motor para
los dominios transaccionales.

## 11. Pruebas y evidencias
Instrucciones en `tests/README.md` y `guion_defensa.md`. Adjuntar en `evidencias/` capturas o video de: creacion de envio,
`409` por transicion invalida, `201/409` por capacidad concurrente, reinicio de Redis, caida de Mongo y recuperacion,
entrega tras reinicio. Resultados reales: _(pegar salida de `pytest` aqui)_.

## 12. Limites y mejoras futuras
- Autenticacion simulada con `X-Rol`: reemplazar por login + JWT.
- Un solo nodo por base: sin replicacion ni alta disponibilidad real.
- La evidencia huerfana temporal (fallo entre Mongo y Postgres) se resuelve por reintento, no automaticamente.
- Fotos solo como URL de texto; falta almacenamiento de archivos (p. ej. objeto/volumen).
- El historial es append-only **a nivel de base de datos** (trigger); un superusuario podria desactivar el trigger, mitigable con permisos y copias de seguridad.
- Worker por sondeo (2 s); alternativa: `LISTEN/NOTIFY` o CDC (Debezium).

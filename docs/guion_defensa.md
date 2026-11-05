# Guion de defensa (15-20 min) - Mensajeria urbana

## Preparacion (antes de entrar)
```powershell
docker compose down -v
docker compose up --build -d
docker compose ps                     # todo healthy/running; esperar ~10 s a que el worker proyecte la semilla
```
Pestanas abiertas: web `http://localhost:8080`, API `http://localhost:8000/docs`, terminal en la carpeta del proyecto,
`docs/matriz_gestores.md` y `docs/diagramas/diagramas.md`. Rol simulado de la web: **administrador** (permite todo).
Envios de la semilla utiles: `ENV-DEMO0001` (creado), `ENV-DEMO0005` (en transito), `ENV-DEMO0006` (entregado con evidencia), `ENV-DEMO0007` (incidencia).

## 1. Problema y dominios (2 min)
- Empresa de mensajeria urbana: registrar paquetes, asignarlos a repartidores, seguimiento y prueba de entrega. Datos ficticios.
- **6 dominios**: envios, despacho, seguimiento, evidencias, consulta operativa, estado temporal.
- Idea central: no hay un gestor "universal"; cada dato vive donde su patron de acceso lo pide, y **PostgreSQL es la fuente de verdad**.
- Mostrar el diagrama de arquitectura (`diagramas.md` #1): web -> API -> modulos -> PostgreSQL / MongoDB / Redis, y worker.

## 2. Matriz de gestores (4 min) - `docs/matriz_gestores.md`
| Dominio | Elegido | Alternativa descartada y por que |
|---|---|---|
| Envios, despacho, eventos | PostgreSQL | MySQL/MongoDB: se necesita unicidad, transacciones multi-tabla, indice unico parcial y `FOR UPDATE` |
| Evidencias | MongoDB | PostgreSQL+JSONB: serviria, pero el dato es heterogeneo y evoluciona sin migraciones |
| Busqueda | MongoDB (proyeccion) | Elasticsearch: cuarto motor innecesario para estos filtros |
| Estado temporal | Redis | Memcached: Redis da TTL consultable y `SCAN` |
- Decir expresamente: **la busqueda y Redis nunca son fuente unica** de una operacion que requiere confirmacion.
- Pregunta de investigacion (resumir): seguimiento como **filas append-only** en PostgreSQL (transaccion con el estado, auditoria, un solo motor) frente a documentos embebidos o event store puro.

## 3. Levantar los servicios (2 min)
```powershell
docker compose up --build -d
docker compose ps
```
Senalar: 3 bases de datos sin puertos publicados (solo red interna), API :8000, web :8080, worker aparte, volumenes persistentes.

## 4. Dos flujos por la web (6 min) - comprobando los gestores
**Flujo A - Solicitud, despacho y aceptacion (3 min)**
1. *Solicitar envio* (cliente): crear envio -> comprobante con codigo `ENV-XXXXXXXX`.
2. *Despacho*: filtro "creado" -> asignar a Repartidor 1 (mostrar la carga 3/3 y que el 2 esta lleno).
3. *Repartidor* -> Repartidor 1: **Aceptar**; mostrar que sin aceptar no se puede retirar.
4. Comprobar en PostgreSQL:
```powershell
docker compose exec postgres psql -U mensajeria_user -d mensajeria -c "SELECT codigo, estado FROM envios ORDER BY id DESC LIMIT 3;"
docker compose exec postgres psql -U mensajeria_user -d mensajeria -c "SELECT estado_anterior, estado_nuevo, actor, detalle FROM eventos_envio ORDER BY fecha DESC LIMIT 6;"
```
**Flujo B - Transito, incidencia y entrega con evidencia (3 min)** (usar `ENV-DEMO0005` ya en transito, o el recien creado)
1. *Repartidor*: enviar posicion simulada (Redis, TTL 60 s) y reportar **incidencia con motivo**.
2. *Despacho > Incidencias abiertas*: el operador **reanuda**.
3. *Repartidor*: **Entregar** con receptor y foto (URL) -> evidencia en Mongo + estado en PostgreSQL.
4. *Seguimiento*: linea de tiempo completa y prueba de entrega; *Detalle*: "Historial coherente: Si".
5. *Despacho > Busqueda rapida*: el envio aparece en la proyeccion (Mongo) con retraso de ~2 s; mostrar `sincronizado`.
```powershell
docker compose exec mongo mongosh -u mongo_admin -p TU_CLAVE --authenticationDatabase admin --quiet --eval "db=db.getSiblingDB('mensajeria'); printjson(db.evidencias.find().sort({registrada_en:-1}).limit(1).toArray())"
docker compose exec redis redis-cli -a TU_CLAVE --no-auth-warning TTL repartidor:1:posicion
```

## 5. Fallo o concurrencia (4 min)
**Concurrencia (2 min)**: `python -m pytest tests\test_capacidad.py -k simultaneas -v`
-> dos asignaciones simultaneas al repartidor de 1 cupo: una `201`, otra `409`. Explicar `SELECT ... FOR UPDATE` sobre el repartidor y el indice unico parcial.
**Caida de Mongo (2 min)**:
```powershell
docker compose stop mongo
```
1. Crear un envio en la web: **funciona** (fuente oficial en PostgreSQL). `Despacho > Busqueda` muestra aviso; `/health` = `degradado`.
2. Intentar una entrega: `503`, el estado **no** cambia (no se entrega sin evidencia).
3. `docker compose start mongo`: el worker vacia la outbox y la busqueda se pone al dia sola.
4. Si se perdiera la proyeccion: `POST /sincronizacion/reconstruir` (en /docs) la regenera desde PostgreSQL.
Extra (si sobra tiempo): `docker compose restart redis` -> posicion "no vigente", historial y evidencias intactos.

## 6. Cambio de requisito y limites (2 min)
| Si piden... | Respuesta |
|---|---|
| Nuevo tipo de servicio | Pantalla Administracion (ya es dato, no codigo) |
| Cambiar capacidad de un repartidor | Administracion; la API valida contra su carga actual |
| Buscar tambien por direccion | Agregar campo al `SELECT` del worker + indice en `init.js` + reconstruir la proyeccion; PostgreSQL no cambia |
| Notificar al cliente al entregar | Nuevo consumidor de la misma outbox |
| Mas de un worker | Ya soportado (`FOR UPDATE SKIP LOCKED`) |
**Limites a nombrar**: autenticacion simulada (`X-Rol`, falta login/JWT); sin transaccion entre Mongo y PostgreSQL (se resuelve con orden de escritura + reintento idempotente);
un solo nodo por base (sin replicacion); fotos solo como URL; worker por sondeo.

## Preguntas probables y respuesta corta
- *Por que el estado esta en `envios` y tambien en el historial?* Lectura rapida + auditoria; se escriben en la misma transaccion y la API verifica `consistente`; si divergieran, manda el historial.
- *Que pasa si Postgres falla despues de guardar la evidencia?* Evidencia huerfana temporal; el reintento con los mismos `evidencia_id`/`evento_id` completa el estado sin duplicar.
- *Por que no una transaccion distribuida?* Los gestores no comparten transaccion ACID; se usa consistencia eventual con outbox y operaciones idempotentes.
- *Como evitas duplicados por reintento?* `evento_id` UUID unico (PK) y `evidencia_id`/`_id = codigo`.
- *Se puede borrar o editar el historial?* No: un trigger en PostgreSQL rechaza UPDATE, DELETE y TRUNCATE.

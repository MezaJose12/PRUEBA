# Matriz de seleccion de gestores

> BORRADOR: la justificacion esta redactada a partir del diseno implementado. Complementala con
> tu propia investigacion (fuentes tecnicas y la "prueba pequena" que pide la Fase 2) y citala en el informe.

| Dominio | Patron de acceso | Estructura | Consistencia | Volumen / disponibilidad | **Elegido** | Alternativa descartada | Por que se descarta |
|---|---|---|---|---|---|---|---|
| Solicitudes y envios | Lectura por codigo, escritura con validacion; cambios de estado frecuentes | Tabular, campos fijos, FK a zonas | Fuerte (ACID): codigo unico y estado coherente | Medio; una instancia basta en el laboratorio | **PostgreSQL** | MySQL | Cumpliria, pero PostgreSQL ofrece indices parciales unicos (un vinculo activo por envio) y `SKIP LOCKED` sin trucos; MongoDB se descarta porque la unicidad y las transacciones multi-tabla son el nucleo del dominio |
| Despacho y asignaciones | Escritura concurrente, regla de capacidad | Relacional (repartidor 1..N asignaciones) | Fuerte: dos asignaciones simultaneas no pueden exceder la capacidad | Bajo | **PostgreSQL** | Redis (contadores atomicos) | Redis daria rapidez, pero la asignacion debe ser duradera y auditable y escribirse en la misma transaccion que el estado del envio |
| Seguimiento y eventos | Solo insercion, lectura ordenada por envio | Tabla append-only (`eventos_envio`) | Fuerte con el estado actual: misma transaccion | Crece sin parar; indice (envio_id, fecha) | **PostgreSQL** | Coleccion de documentos / Event store dedicado | Documentos embebidos haria crecer sin limite un documento y separaria historial y estado en dos gestores sin transaccion conjunta; un event store dedicado anade un motor sin necesidad (ver pregunta de investigacion) |
| Evidencias de entrega | Escritura una vez, lectura por codigo | Documento heterogeneo (receptor, observacion, foto/URL, campos futuros) | Fuerte por documento; `_id` = codigo evita duplicados | Bajo-medio; podria crecer con archivos | **MongoDB** | PostgreSQL con JSONB | JSONB serviria, pero el enunciado pide datos heterogeneos y asi se justifica un segundo modelo; MongoDB permite evolucionar el esquema sin migraciones. Es un riesgo aceptado: no hay transaccion conjunta con Postgres (ver tabla de consistencia) |
| Consulta operativa (busqueda) | Filtros por codigo, zona, estado, destinatario (texto) y rango de fechas | Documento desnormalizado (un doc por envio) | Eventual: es una proyeccion reconstruible | Lectura intensiva | **MongoDB** (proyeccion) | Elasticsearch | Mas potente para texto, pero agrega un cuarto motor pesado; con los filtros del enunciado bastan indices de MongoDB y el enunciado dice que no se premia anadir gestores sin necesidad |
| Estado temporal (posicion/conexion) | Escrituras muy frecuentes, lectura de "ultimo valor" | Clave-valor con expiracion | Eventual/efimera; perderla es aceptable | Muy rapido, en memoria | **Redis** | Memcached | Memcached tambien expira claves, pero Redis ofrece TTL consultable (`TTL`), `SCAN` por patron para listar posiciones vigentes y estructuras utiles si el dominio crece |

## Resumen de motores (minimo exigido: 3 con propositos distintos)
- **PostgreSQL**: relacional, transaccional. Fuente oficial de envios, asignaciones, eventos y outbox.
- **MongoDB**: documentos. Evidencias (dato oficial) y vista de busqueda (dato derivado).
- **Redis**: clave-valor en memoria con TTL. Solo datos efimeros.

# Mensajeria urbana - Persistencia poliglota (Proyecto B)

PostgreSQL (fuente oficial) + MongoDB (evidencias y busqueda) + Redis (estado temporal), API FastAPI,
worker de sincronizacion (outbox) y frontend web, todo con Docker Compose.

## Requisitos
Docker y Docker Compose. (Para las pruebas: Python 3.10+ en tu maquina.)

## Ejecucion
```bash
cp .env.example .env              # cambia las claves ficticias si quieres
docker compose up --build -d
docker compose ps                 # postgres, mongo, redis healthy; api, worker, web running
```
| Que | URL |
|---|---|
| Interfaz web | http://localhost:8080 |
| API + OpenAPI interactivo | http://localhost:8000/docs |
| Salud | http://localhost:8000/health |

Las bases de datos NO publican puertos al equipo (solo la red interna de Docker).
El selector **"Rol simulado"** de la barra superior cambia el encabezado `X-Rol` (la API valida permisos; ver `api/app/seguridad.py`).

## Datos de ejemplo (semilla)
Al crear la base se cargan 8 envios en distintos estados (`ENV-DEMO0001` ... `ENV-DEMO0008`):
creado (x2), asignado, retirado, en transito, **entregado con evidencia**, **con incidencia** y cancelado.
El repartidor 2 queda lleno (2/2) para demostrar el control de capacidad.
> Si ya habias levantado una version anterior, ejecuta `docker compose down -v` antes de volver a levantar:
> el esquema y la semilla solo se aplican cuando el volumen esta vacio.

## Recorrido rapido por la web
1. **Solicitar envio** -> obtienes el codigo `ENV-XXXXXXXX`.
2. **Despacho** -> filtro "creado", asigna un repartidor (la capacidad se valida en el servidor).
3. **Repartidor** -> elige al repartidor: Aceptar (o Rechazar) la asignacion, Retirar, En transito, Incidencia (con motivo), Entregar con evidencia.
   Las incidencias las resuelve el operador en **Despacho > Incidencias abiertas**.
4. **Seguimiento / Detalle** -> linea de tiempo y prueba de entrega.
5. **Despacho > Busqueda rapida** -> consulta sobre el indice en MongoDB.
6. **Administracion** -> zonas, tipos de servicio y repartidores (rol administrador).

## Demo por consola y pruebas
```bash
python3 scripts/demo.py                       # flujos 1-5 con salida paso a paso
pip install -r tests/requirements.txt
pytest tests/test_estados.py                  # unitarias (sin Docker)
pytest tests/                                 # integracion (API activa; algunas reinician contenedores)
scripts/exportar_openapi.sh                   # guarda docs/openapi.json
```

## Reinicio y limpieza
```bash
docker compose restart            # reinicia sin perder datos
docker compose down               # apaga y CONSERVA los volumenes (datos)
docker compose down -v            # apaga y BORRA los datos (re-ejecuta init.sql / init.js)
```

## Pruebas de fallo para la defensa
```bash
docker compose stop mongo         # el registro sigue; /buscar = 503; /health = degradado
docker compose start mongo        # el worker se pone al dia solo
docker compose restart redis      # se pierde lo efimero; historial y evidencias intactos
```

## Estructura
```
db/postgres/init.sql     esquema + datos semilla (Source of Truth)
db/mongo/init.js         indices de busqueda y evidencias
api/app/main.py          arranque de FastAPI y routers
api/app/config.py        variables de entorno
api/app/seguridad.py     roles simulados (X-Rol)
api/app/services.py      cambio de estado transaccional compartido
api/app/domain/          maquina de estados y regla de capacidad (logica pura)
api/app/repositories/    conexiones a Postgres, Mongo y Redis
api/app/routers/         health, envios, despacho, evidencias, posiciones, buscar, admin
api/app/worker.py        sincronizador outbox -> Mongo
web/                     6 pantallas (HTML/JS) + nginx
tests/  scripts/         pruebas y demo
docs/                    informe, matriz, consistencia, diagramas, API, guion de defensa
```

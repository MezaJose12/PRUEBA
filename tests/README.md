# Pruebas

```bash
pip install -r tests/requirements.txt
pytest tests/test_estados.py     # unitarias: no necesitan Docker
docker compose up --build -d
pytest tests/                    # integracion: necesitan la API activa
```

| Archivo | Que demuestra | Prueba de la defensa |
|---|---|---|
| test_estados.py | Transiciones validas/invalidas y regla de capacidad (sin BD) | 2 |
| test_idempotencia.py | Reintento con el mismo evento_id no duplica; 409 en transicion invalida | 2 |
| test_capacidad.py | Dos asignaciones simultaneas: solo una gana; entregar libera cupo; roles | 3 |
| test_evidencias.py | Entrega con evidencia, reintento idempotente, estado = ultimo evento | 5 |
| test_reglas.py | Aceptar/rechazar asignacion, incidencias con motivo, roles (403), tipos de servicio, semilla coherente | 2 y 3 |
| test_busqueda.py | La proyeccion en Mongo se actualiza (consistencia eventual) | flujo 5 |
| test_sincronizacion.py | Mongo caido: el registro sigue; al volver se sincroniza; reconstruccion | 5 |
| test_fallos.py | Redis reiniciado pierde lo efimero, no el historial; entrega sobrevive a reinicios; historial inmutable en la BD | 4 y 5 |

Los tests de Docker (`test_sincronizacion.py`, `test_fallos.py`) detienen/reinician contenedores:
ejecutelos desde la raiz del proyecto. Se omiten solos si Docker no esta disponible.

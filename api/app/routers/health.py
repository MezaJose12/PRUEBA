"""
routers/health.py - GET /health

Comprueba si la API y sus dependencias responden. Sirve para:
  - ver rapido que todo esta arriba,
  - demostrar en la defensa que "si Mongo cae, la API sigue funcionando" (estado 'degradado').
No devuelve contrasenas ni datos sensibles.
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.repositories import mongo, pg
from app.repositories.redis_repo import cliente as redis_cliente

router = APIRouter(tags=["salud"])


def _probar(funcion) -> str:
    """Ejecuta una comprobacion y devuelve 'ok' o 'caido'."""
    try:
        funcion()
        return "ok"
    except Exception:
        return "caido"


def _ping_postgres() -> None:
    with pg.conectar() as conn:
        conn.execute("SELECT 1")


@router.get("/health")
def health():
    dependencias = {
        "postgres": _probar(_ping_postgres),
        "mongo": _probar(mongo.ping),
        "redis": _probar(redis_cliente.ping),
    }
    if dependencias["postgres"] == "caido":
        # Sin Postgres no se puede operar: 503 = servicio no disponible
        return JSONResponse(status_code=503, content={"estado": "caido", "dependencias": dependencias})

    estado = "ok" if all(v == "ok" for v in dependencias.values()) else "degradado"
    return {"estado": estado, "dependencias": dependencias}

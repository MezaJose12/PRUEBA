"""
routers/posiciones.py - Estado temporal del repartidor en Redis (con TTL).

  PUT /repartidores/{id}/posicion   guarda la ultima posicion simulada (expira sola)
  GET /repartidores/{id}/posicion   devuelve la posicion o 'no vigente' si ya expiro
  GET /posiciones                   todas las posiciones vigentes

Redis NO es fuente de verdad: si se reinicia, estos datos se pierden y es lo esperado.
El historial de envios (Postgres) y las evidencias (Mongo) no dependen de Redis.
El TTL lo fija el SERVIDOR (TTL_POSICION_SEGUNDOS), no el navegador.
"""
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from redis.exceptions import RedisError

from app.config import settings
from app.repositories import pg
from app.repositories.redis_repo import cliente as redis
from app.seguridad import requiere_rol

router = APIRouter(tags=["estado-temporal"])


class Posicion(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


def _clave(repartidor_id: int) -> str:
    return f"repartidor:{repartidor_id}:posicion"


def _leer(repartidor_id: int) -> dict:
    """Lee de Redis. Si la clave no existe (expiro o nunca se guardo) -> vigente = False."""
    valor = redis.get(_clave(repartidor_id))
    if valor is None:
        return {"repartidor_id": repartidor_id, "vigente": False, "conexion": "no vigente"}
    return {"repartidor_id": repartidor_id, "vigente": True, "conexion": "conectado",
            "ttl_restante": redis.ttl(_clave(repartidor_id)), **json.loads(valor)}


@router.put("/repartidores/{repartidor_id}/posicion", dependencies=[Depends(requiere_rol("repartidor", "administrador"))])
def guardar_posicion(repartidor_id: int, datos: Posicion):
    with pg.conectar() as conn:
        if conn.execute("SELECT 1 FROM repartidores WHERE id = %s", (repartidor_id,)).fetchone() is None:
            raise HTTPException(status_code=404, detail="Repartidor no encontrado")
    carga = json.dumps({"lat": datos.lat, "lon": datos.lon,
                        "actualizado": datetime.now(timezone.utc).isoformat()})
    try:
        redis.set(_clave(repartidor_id), carga, ex=settings.ttl_posicion)   # ex = expira en N segundos
    except RedisError:
        raise HTTPException(status_code=503, detail="Servicio de estado temporal no disponible")
    return _leer(repartidor_id)


@router.get("/repartidores/{repartidor_id}/posicion")
def consultar_posicion(repartidor_id: int):
    try:
        return _leer(repartidor_id)
    except RedisError:
        raise HTTPException(status_code=503, detail="Servicio de estado temporal no disponible")


@router.get("/posiciones")
def listar_posiciones():
    try:
        ids = sorted(int(k.split(":")[1]) for k in redis.scan_iter(match="repartidor:*:posicion"))
        return [_leer(i) for i in ids]
    except RedisError:
        raise HTTPException(status_code=503, detail="Servicio de estado temporal no disponible")

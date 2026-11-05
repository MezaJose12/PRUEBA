"""
routers/admin.py - Mantenimiento (rol administrador): zonas y repartidores.

  GET   /zonas                 (publico: lo usa el formulario de solicitud)
  POST  /zonas                 PATCH /zonas/{id}
  POST  /repartidores          PATCH /repartidores/{id}    (GET /repartidores esta en despacho.py)
  GET   /tipos-servicio        POST /tipos-servicio        PATCH /tipos-servicio/{id}
"""
import psycopg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.repositories import pg
from app.seguridad import requiere_rol

router = APIRouter(tags=["administracion"])
solo_admin = [Depends(requiere_rol("administrador"))]


class ZonaIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=60)


class RepartidorIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=100)
    capacidad_max: int = Field(gt=0, le=50)


class RepartidorPatch(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=100)
    capacidad_max: int | None = Field(default=None, gt=0, le=50)
    activo: bool | None = None


@router.get("/zonas")
def listar_zonas():
    with pg.conectar() as conn:
        return conn.execute("SELECT * FROM zonas ORDER BY id").fetchall()


@router.post("/zonas", status_code=201, dependencies=solo_admin)
def crear_zona(datos: ZonaIn):
    try:
        with pg.conectar() as conn:
            return conn.execute("INSERT INTO zonas (nombre) VALUES (%s) RETURNING *", (datos.nombre,)).fetchone()
    except psycopg.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="Ya existe una zona con ese nombre")


@router.patch("/zonas/{zona_id}", dependencies=solo_admin)
def renombrar_zona(zona_id: int, datos: ZonaIn):
    try:
        with pg.conectar() as conn:
            z = conn.execute("UPDATE zonas SET nombre = %s WHERE id = %s RETURNING *",
                             (datos.nombre, zona_id)).fetchone()
    except psycopg.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="Ya existe una zona con ese nombre")
    if z is None:
        raise HTTPException(status_code=404, detail="Zona no encontrada")
    return z


@router.post("/repartidores", status_code=201, dependencies=solo_admin)
def crear_repartidor(datos: RepartidorIn):
    with pg.conectar() as conn:
        return conn.execute("INSERT INTO repartidores (nombre, capacidad_max) VALUES (%s, %s) RETURNING *",
                            (datos.nombre, datos.capacidad_max)).fetchone()


@router.patch("/repartidores/{repartidor_id}", dependencies=solo_admin)
def editar_repartidor(repartidor_id: int, datos: RepartidorPatch):
    with pg.conectar() as conn:
        # Se bloquea al repartidor: asi no cambia su capacidad mientras alguien le asigna un envio
        r = conn.execute("SELECT * FROM repartidores WHERE id = %s FOR UPDATE", (repartidor_id,)).fetchone()
        if r is None:
            raise HTTPException(status_code=404, detail="Repartidor no encontrado")
        nuevo = {**r, **datos.model_dump(exclude_none=True)}
        carga = conn.execute("SELECT COUNT(*) AS n FROM asignaciones WHERE repartidor_id = %s AND activa",
                             (repartidor_id,)).fetchone()["n"]
        if nuevo["capacidad_max"] < carga:
            raise HTTPException(status_code=409,
                                detail=f"No se puede bajar la capacidad a {nuevo['capacidad_max']}: tiene {carga} envios activos")
        return conn.execute(
            "UPDATE repartidores SET nombre = %s, capacidad_max = %s, activo = %s WHERE id = %s RETURNING *",
            (nuevo["nombre"], nuevo["capacidad_max"], nuevo["activo"], repartidor_id)).fetchone()


# ----------------------------- Tipos de servicio -----------------------------
class TipoIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=40)


class TipoPatch(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=40)
    activo: bool | None = None


@router.get("/tipos-servicio")
def listar_tipos(todos: bool = False):
    """Por defecto solo los activos (los que se ofrecen al cliente). ?todos=true incluye desactivados."""
    with pg.conectar() as conn:
        return conn.execute(f"SELECT * FROM tipos_servicio {'' if todos else 'WHERE activo'} ORDER BY id").fetchall()


@router.post("/tipos-servicio", status_code=201, dependencies=solo_admin)
def crear_tipo(datos: TipoIn):
    try:
        with pg.conectar() as conn:
            return conn.execute("INSERT INTO tipos_servicio (nombre) VALUES (%s) RETURNING *", (datos.nombre,)).fetchone()
    except psycopg.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="Ya existe un tipo de servicio con ese nombre")


@router.patch("/tipos-servicio/{tipo_id}", dependencies=solo_admin)
def editar_tipo(tipo_id: int, datos: TipoPatch):
    try:
        with pg.conectar() as conn:
            t = conn.execute("SELECT * FROM tipos_servicio WHERE id = %s FOR UPDATE", (tipo_id,)).fetchone()
            if t is None:
                raise HTTPException(status_code=404, detail="Tipo de servicio no encontrado")
            nuevo = {**t, **datos.model_dump(exclude_none=True)}
            return conn.execute("UPDATE tipos_servicio SET nombre = %s, activo = %s WHERE id = %s RETURNING *",
                                (nuevo["nombre"], nuevo["activo"], tipo_id)).fetchone()
    except psycopg.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="Ya existe un tipo de servicio con ese nombre")

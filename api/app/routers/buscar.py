"""
routers/buscar.py - Consulta operativa sobre la PROYECCION en MongoDB.

  GET  /buscar?codigo=&zona=&estado=&destinatario=&desde=&hasta=
  GET  /sincronizacion/estado        cuantos avisos pendientes hay y si hay desfase
  POST /sincronizacion/reconstruir   vuelve a proyectar TODOS los envios desde Postgres

La busqueda puede ir con RETRASO (consistencia eventual): el dato oficial esta en Postgres.
Si Mongo cae, /buscar responde 503 pero crear, asignar y entregar siguen funcionando.
"""
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pymongo.errors import PyMongoError

from app.repositories import mongo, pg
from app.seguridad import requiere_rol

router = APIRouter(tags=["busqueda"])


@router.get("/buscar")
def buscar(codigo: str | None = None, zona: str | None = None, estado: str | None = None,
           destinatario: str | None = None, desde: datetime | None = None,
           hasta: datetime | None = None, limite: int = 50):
    filtro: dict = {}
    if codigo:
        filtro["_id"] = codigo.upper()
    if zona:
        filtro["zona"] = zona
    if estado:
        filtro["estado"] = estado
    if destinatario:
        # re.escape evita que el texto del usuario se interprete como expresion regular
        filtro["destinatario"] = {"$regex": re.escape(destinatario), "$options": "i"}
    if desde or hasta:
        rango = {}
        if desde: rango["$gte"] = desde
        if hasta: rango["$lte"] = hasta
        filtro["creado_en"] = rango
    try:
        docs = list(mongo.obtener_db()["envios_busqueda"].find(filtro).sort("creado_en", -1)
                    .limit(max(1, min(limite, 200))))
    except PyMongoError:
        raise HTTPException(status_code=503,
                            detail="El indice de busqueda no esta disponible. Use el listado oficial (GET /envios).")
    return {"fuente": "mongodb (proyeccion, puede ir con retraso)", "total": len(docs), "resultados": docs}


@router.get("/sincronizacion/estado")
def estado_sincronizacion():
    """Pantalla tecnica opcional: sin credenciales ni datos sensibles."""
    with pg.conectar() as conn:
        o = conn.execute(
            """SELECT COUNT(*) FILTER (WHERE NOT procesado) AS pendientes,
                      COUNT(*) FILTER (WHERE procesado)     AS procesados,
                      MAX(procesado_en)                     AS ultimo_procesado
               FROM outbox"""
        ).fetchone()
        total_pg = conn.execute("SELECT COUNT(*) AS n FROM envios").fetchone()["n"]
    try:
        total_mongo = mongo.obtener_db()["envios_busqueda"].count_documents({})
    except PyMongoError:
        total_mongo = None
    return {"outbox": o, "envios_postgres": total_pg, "envios_en_busqueda": total_mongo,
            "mongo_disponible": total_mongo is not None,
            "sincronizado": total_mongo == total_pg and o["pendientes"] == 0}


@router.post("/sincronizacion/reconstruir", dependencies=[Depends(requiere_rol("operador", "administrador"))])
def reconstruir_proyeccion():
    """RECUPERACION: la proyeccion se puede perder (no es fuente de verdad). Esto encola un aviso
    por cada envio y el worker la reconstruye completa desde PostgreSQL."""
    with pg.conectar() as conn:
        n = conn.execute("INSERT INTO outbox (envio_id) SELECT id FROM envios").rowcount
    return {"avisos_encolados": n}

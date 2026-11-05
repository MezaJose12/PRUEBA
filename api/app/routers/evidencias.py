"""
routers/evidencias.py - Prueba de entrega (MongoDB, coleccion 'evidencias').

  POST /envios/{codigo}/entrega     confirma la entrega: guarda evidencia + estado 'entregado'
  GET  /envios/{codigo}/evidencia   consulta la evidencia

ORDEN DE ESCRITURA (no hay transaccion ACID entre Mongo y Postgres):
  1) Mongo: se guarda la evidencia (_id = codigo del envio -> solo una por envio).
  2) Postgres: una transaccion cambia el estado a 'entregado' + evento + outbox.
Fallos posibles:
  - Mongo caido      -> 503 y NO se cambia el estado (no se entrega sin evidencia).
  - Postgres falla   -> la evidencia queda guardada; el cliente REINTENTA con los mismos
                        evidencia_id/evento_id y todo se completa sin duplicar nada.
La evidencia confirmada es dato OFICIAL (no es cache): no se borra ni se reconstruye.
"""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.domain.estados import EstadoEnvio
from app.repositories import mongo, pg
from app.seguridad import requiere_rol
from app.services import cambiar_estado_tx

router = APIRouter(tags=["evidencias"])


class Entrega(BaseModel):
    receptor: str = Field(min_length=2, max_length=100)
    observacion: str = Field(default="", max_length=500)
    foto_url: str | None = Field(default=None, max_length=300)   # foto SIMULADA (solo una URL de texto)
    actor: str = Field(min_length=2, max_length=100)
    evidencia_id: UUID    # idempotencia de la evidencia
    evento_id: UUID       # idempotencia del cambio de estado


@router.post("/envios/{codigo}/entrega", status_code=201,
             dependencies=[Depends(requiere_rol("repartidor", "administrador"))])
def confirmar_entrega(codigo: str, datos: Entrega, response: Response):
    # Lectura previa (sin bloqueo) para no guardar evidencia de un envio que no puede entregarse
    with pg.conectar() as conn:
        envio = conn.execute("SELECT estado FROM envios WHERE codigo = %s", (codigo,)).fetchone()
    if envio is None:
        raise HTTPException(status_code=404, detail="Envio no encontrado")
    if envio["estado"] not in (EstadoEnvio.EN_TRANSITO.value, EstadoEnvio.ENTREGADO.value):
        raise HTTPException(status_code=409,
                            detail=f"Solo se entrega desde 'en_transito' (estado actual: {envio['estado']})")

    # 1) Evidencia en Mongo
    doc = {"_id": codigo, "evidencia_id": str(datos.evidencia_id), "codigo_envio": codigo,
           "receptor": datos.receptor, "observacion": datos.observacion, "foto_url": datos.foto_url,
           "actor": datos.actor, "registrada_en": datetime.now(timezone.utc)}
    try:
        mongo.obtener_db()["evidencias"].insert_one(doc)
    except DuplicateKeyError:
        existente = mongo.obtener_db()["evidencias"].find_one({"_id": codigo})
        if existente and existente.get("evidencia_id") != str(datos.evidencia_id):
            raise HTTPException(status_code=409, detail="El envio ya tiene una evidencia distinta registrada")
        # misma evidencia_id: es un reintento -> se continua
    except PyMongoError:
        raise HTTPException(status_code=503,
                            detail="Almacen de evidencias no disponible; la entrega NO se registro. Reintente.")

    # 2) Estado en Postgres (misma regla transaccional que cualquier cambio de estado)
    with pg.conectar() as conn:
        envio, repetido = cambiar_estado_tx(conn, codigo, EstadoEnvio.ENTREGADO, datos.actor,
                                            datos.evento_id, detalle=f"Recibido por {datos.receptor}", desde_entrega=True)
    if repetido:
        response.status_code = 200
    doc["registrada_en"] = doc["registrada_en"].isoformat()
    return {"envio": envio, "evidencia": doc, "repetido": repetido}


@router.get("/envios/{codigo}/evidencia")
def consultar_evidencia(codigo: str):
    try:
        doc = mongo.obtener_db()["evidencias"].find_one({"_id": codigo})
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Almacen de evidencias no disponible")
    if doc is None:
        raise HTTPException(status_code=404, detail="Este envio no tiene evidencia registrada")
    doc.pop("_id", None)
    return doc

"""
routers/despacho.py - Asignacion de repartidores con control de capacidad.

  GET   /repartidores                      lista con carga actual y disponibilidad
  GET   /repartidores/{id}/tareas          envios activos del repartidor
  POST  /asignaciones                      asigna un repartidor a un envio (creado -> asignado)
  PATCH /asignaciones/{id}/aceptar         el repartidor ACEPTA (requisito para retirar el paquete)
  PATCH /asignaciones/{id}/rechazar        el repartidor rechaza ANTES de aceptar (vuelve a 'creado')
  PATCH /asignaciones/{id}/liberar         el operador libera (asignado -> creado) para reasignar

CONTROL DE CONCURRENCIA (prueba 3 de la defensa)
------------------------------------------------
Si dos operadores asignan a la vez envios distintos al mismo repartidor con 1 solo cupo:
  1) Ambas peticiones intentan "SELECT ... FOR UPDATE" sobre la fila del repartidor.
  2) PostgreSQL deja pasar a UNA y hace esperar a la otra.
  3) La primera cuenta su carga (0), asigna y confirma (COMMIT).
  4) La segunda se desbloquea, cuenta su carga (ahora 1) y recibe 409 (sin cupo).
Orden de bloqueos: primero repartidor, luego envio (siempre igual -> sin interbloqueos).
"""
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from app.domain.capacidad import puede_recibir
from app.domain.estados import EstadoEnvio
from app.repositories import pg
from app.seguridad import requiere_rol

router = APIRouter(tags=["despacho"])
solo_operacion = [Depends(requiere_rol("operador", "administrador"))]       # quien despacha
solo_repartidor = [Depends(requiere_rol("repartidor", "administrador"))]    # quien acepta/rechaza


class SolicitudAsignacion(BaseModel):
    codigo_envio: str = Field(min_length=3, max_length=40)
    repartidor_id: int = Field(gt=0)
    actor: str = Field(min_length=2, max_length=100)   # operador que asigna (auditoria)
    evento_id: UUID                                     # idempotencia: reintento seguro


class AccionAsignacion(BaseModel):
    """Cuerpo comun de aceptar / rechazar / liberar."""
    actor: str = Field(min_length=2, max_length=100)
    evento_id: UUID


def _registrar_cambio(conn, envio_id: int, anterior: str, nuevo: str, actor: str,
                      evento_id: UUID, detalle: str | None = None) -> None:
    """Escribe el evento de historial y el aviso de outbox (siempre juntos, en la transaccion)."""
    conn.execute(
        """INSERT INTO eventos_envio (evento_id, envio_id, estado_anterior, estado_nuevo, actor, detalle)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (evento_id, envio_id, anterior, nuevo, actor, detalle),
    )
    conn.execute("INSERT INTO outbox (envio_id) VALUES (%s)", (envio_id,))


def _evento_repetido(conn, evento_id: UUID) -> bool:
    return conn.execute("SELECT 1 FROM eventos_envio WHERE evento_id = %s", (evento_id,)).fetchone() is not None


@router.get("/repartidores")
def listar_repartidores():
    """Repartidores con su carga actual (asignaciones activas) y si tienen cupo."""
    with pg.conectar() as conn:
        filas = conn.execute(
            """SELECT r.id, r.nombre, r.capacidad_max, r.activo,
                      COUNT(a.id) FILTER (WHERE a.activa) AS carga_actual
               FROM repartidores r
               LEFT JOIN asignaciones a ON a.repartidor_id = r.id
               GROUP BY r.id ORDER BY r.id"""
        ).fetchall()
    for f in filas:
        f["disponible"] = f["activo"] and puede_recibir(f["carga_actual"], f["capacidad_max"])
    return filas


@router.get("/repartidores/{repartidor_id}/tareas")
def tareas_repartidor(repartidor_id: int):
    """Envios con asignacion ACTIVA para este repartidor (su lista de trabajo)."""
    with pg.conectar() as conn:
        return conn.execute(
            """SELECT e.codigo, e.destinatario, e.origen, e.destino, e.estado, z.nombre AS zona,
                      a.id AS asignacion_id, (a.aceptada_en IS NOT NULL) AS aceptada
               FROM asignaciones a
               JOIN envios e ON e.id = a.envio_id JOIN zonas z ON z.id = e.zona_id
               WHERE a.repartidor_id = %s AND a.activa ORDER BY a.creada_en""",
            (repartidor_id,),
        ).fetchall()


@router.post("/asignaciones", status_code=201, dependencies=solo_operacion)
def asignar(datos: SolicitudAsignacion, response: Response):
    """Asigna un repartidor a un envio.

    201 -> asignado | 200 -> reintento ya aplicado | 404 -> envio/repartidor no existe
    409 -> sin capacidad, repartidor inactivo o el envio no esta en estado 'creado'
    """
    with pg.conectar() as conn:
        # 1) Bloquear al repartidor: serializa las asignaciones concurrentes hacia el.
        repartidor = conn.execute(
            "SELECT * FROM repartidores WHERE id = %s FOR UPDATE", (datos.repartidor_id,)
        ).fetchone()
        if repartidor is None:
            raise HTTPException(status_code=404, detail="Repartidor no encontrado")

        # 2) Bloquear el envio.
        envio = conn.execute(
            "SELECT * FROM envios WHERE codigo = %s FOR UPDATE", (datos.codigo_envio,)
        ).fetchone()
        if envio is None:
            raise HTTPException(status_code=404, detail="Envio no encontrado")

        # 3) Idempotencia: si este evento_id ya se registro, es un reintento.
        if _evento_repetido(conn, datos.evento_id):
            response.status_code = 200
            return {"envio": envio, "repetido": True}

        # 4) Validaciones de negocio
        if not repartidor["activo"]:
            raise HTTPException(status_code=409, detail="El repartidor esta inactivo")

        actual = EstadoEnvio(envio["estado"])
        if not actual.puede_pasar_a(EstadoEnvio.ASIGNADO):
            raise HTTPException(
                status_code=409,
                detail=f"Transicion invalida: {actual.value} -> asignado (solo se asigna desde 'creado')",
            )

        carga = conn.execute(
            "SELECT COUNT(*) AS n FROM asignaciones WHERE repartidor_id = %s AND activa",
            (datos.repartidor_id,),
        ).fetchone()["n"]
        if not puede_recibir(carga, repartidor["capacidad_max"]):
            raise HTTPException(
                status_code=409,
                detail=f"Repartidor sin capacidad ({carga}/{repartidor['capacidad_max']})",
            )

        # 5) Escrituras (todas en la misma transaccion)
        try:
            asignacion = conn.execute(
                "INSERT INTO asignaciones (envio_id, repartidor_id) VALUES (%s, %s) RETURNING *",
                (envio["id"], datos.repartidor_id),
            ).fetchone()
        except psycopg.errors.UniqueViolation:
            raise HTTPException(status_code=409, detail="El envio ya tiene una asignacion activa")

        envio = conn.execute(
            "UPDATE envios SET estado = 'asignado', actualizado_en = now() WHERE id = %s RETURNING *",
            (envio["id"],),
        ).fetchone()
        _registrar_cambio(conn, envio["id"], actual.value, "asignado", datos.actor, datos.evento_id,
                          f"Asignado a {repartidor['nombre']}")
    return {"asignacion": asignacion, "envio": envio, "repetido": False}


@router.patch("/asignaciones/{asignacion_id}/aceptar", dependencies=solo_repartidor)
def aceptar(asignacion_id: int, datos: AccionAsignacion):
    """El repartidor acepta la asignacion. Sin aceptar NO puede pasar el envio a 'retirado'.
    El estado del envio sigue siendo 'asignado'; queda un evento de auditoria con la aceptacion."""
    with pg.conectar() as conn:
        previa = conn.execute("SELECT envio_id FROM asignaciones WHERE id = %s", (asignacion_id,)).fetchone()
        if previa is None:
            raise HTTPException(status_code=404, detail="Asignacion no encontrada")
        envio = conn.execute("SELECT * FROM envios WHERE id = %s FOR UPDATE", (previa["envio_id"],)).fetchone()
        if _evento_repetido(conn, datos.evento_id):
            return {"envio": envio, "repetido": True}
        asig = conn.execute("SELECT * FROM asignaciones WHERE id = %s FOR UPDATE", (asignacion_id,)).fetchone()
        if not asig["activa"]:
            raise HTTPException(status_code=409, detail="La asignacion ya no esta activa")
        if asig["aceptada_en"] is not None:
            raise HTTPException(status_code=409, detail="La asignacion ya fue aceptada")
        if envio["estado"] != "asignado":
            raise HTTPException(status_code=409, detail=f"No se puede aceptar con el envio en '{envio['estado']}'")
        asig = conn.execute("UPDATE asignaciones SET aceptada_en = now() WHERE id = %s RETURNING *",
                            (asignacion_id,)).fetchone()
        _registrar_cambio(conn, envio["id"], "asignado", "asignado", datos.actor, datos.evento_id,
                          "Asignacion aceptada por el repartidor")
    return {"asignacion": asig, "envio": envio, "repetido": False}


def _liberar_tx(conn, asignacion_id: int, datos: AccionAsignacion, detalle: str, solo_sin_aceptar: bool):
    """Cierra la asignacion y devuelve el envio a 'creado' (dentro de la transaccion abierta)."""
    previa = conn.execute("SELECT envio_id FROM asignaciones WHERE id = %s", (asignacion_id,)).fetchone()
    if previa is None:
        raise HTTPException(status_code=404, detail="Asignacion no encontrada")
    envio = conn.execute("SELECT * FROM envios WHERE id = %s FOR UPDATE", (previa["envio_id"],)).fetchone()
    if _evento_repetido(conn, datos.evento_id):
        return envio, True
    asig = conn.execute("SELECT * FROM asignaciones WHERE id = %s FOR UPDATE", (asignacion_id,)).fetchone()
    if not asig["activa"]:
        raise HTTPException(status_code=409, detail="La asignacion ya estaba liberada")
    if solo_sin_aceptar and asig["aceptada_en"] is not None:
        raise HTTPException(status_code=409, detail="Ya la acepto: solo el operador puede liberarla")
    actual = EstadoEnvio(envio["estado"])
    if not actual.puede_pasar_a(EstadoEnvio.CREADO):
        raise HTTPException(status_code=409, detail=f"No se puede liberar con el envio en estado '{actual.value}'")
    conn.execute("UPDATE asignaciones SET activa = FALSE WHERE id = %s", (asignacion_id,))
    envio = conn.execute(
        "UPDATE envios SET estado = 'creado', actualizado_en = now() WHERE id = %s RETURNING *", (envio["id"],)
    ).fetchone()
    _registrar_cambio(conn, envio["id"], actual.value, "creado", datos.actor, datos.evento_id, detalle)
    return envio, False


@router.patch("/asignaciones/{asignacion_id}/liberar", dependencies=solo_operacion)
def liberar(asignacion_id: int, datos: AccionAsignacion):
    """El operador libera la asignacion (antes del retiro) para poder reasignar."""
    with pg.conectar() as conn:
        envio, repetido = _liberar_tx(conn, asignacion_id, datos, "Asignacion liberada por el operador", False)
    return {"envio": envio, "repetido": repetido}


@router.patch("/asignaciones/{asignacion_id}/rechazar", dependencies=solo_repartidor)
def rechazar(asignacion_id: int, datos: AccionAsignacion):
    """El repartidor rechaza la asignacion (solo antes de aceptarla). El envio vuelve a 'creado'."""
    with pg.conectar() as conn:
        envio, repetido = _liberar_tx(conn, asignacion_id, datos, "Asignacion rechazada por el repartidor", True)
    return {"envio": envio, "repetido": repetido}

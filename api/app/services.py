"""
services.py - Logica de cambio de estado compartida por varios endpoints.

La usan:  PATCH /envios/{codigo}/estado   y   POST /envios/{codigo}/entrega
Asi la regla "estado + historial + outbox en UNA transaccion" existe en un solo lugar.
"""
from uuid import UUID

from fastapi import HTTPException

from app.domain.estados import LIBERAN_CAPACIDAD, EstadoEnvio


def cambiar_estado_tx(conn, codigo: str, nuevo: EstadoEnvio, actor: str, evento_id: UUID,
                      detalle: str | None = None, desde_entrega: bool = False) -> tuple[dict, bool]:
    """Aplica un cambio de estado DENTRO de la transaccion abierta (conn).

    Devuelve (envio, repetido). Lanza HTTPException 404 / 409 / 422 si no procede.
    desde_entrega=True solo lo usa el endpoint de entrega (que exige evidencia).
    """
    # FOR UPDATE: si dos peticiones tocan el mismo envio, la segunda espera a la primera.
    envio = conn.execute("SELECT * FROM envios WHERE codigo = %s FOR UPDATE", (codigo,)).fetchone()
    if envio is None:
        raise HTTPException(status_code=404, detail="Envio no encontrado")

    # IDEMPOTENCIA: un evento_id ya registrado es un reintento -> no se repite el cambio.
    previo = conn.execute("SELECT envio_id FROM eventos_envio WHERE evento_id = %s", (evento_id,)).fetchone()
    if previo:
        if previo["envio_id"] != envio["id"]:
            raise HTTPException(status_code=409, detail="El evento_id ya fue usado en otro envio")
        return envio, True

    # Estados que solo se alcanzan por su endpoint especifico
    if nuevo == EstadoEnvio.ASIGNADO:
        raise HTTPException(status_code=409, detail="Para asignar use POST /asignaciones (requiere repartidor)")
    if nuevo == EstadoEnvio.ENTREGADO and not desde_entrega:
        raise HTTPException(status_code=409,
                            detail="Para entregar use POST /envios/{codigo}/entrega (requiere evidencia)")

    actual = EstadoEnvio(envio["estado"])
    if not actual.puede_pasar_a(nuevo):
        raise HTTPException(status_code=409, detail=f"Transicion invalida: {actual.value} -> {nuevo.value}")

    # Regla: una incidencia SIEMPRE lleva motivo (auditoria)
    if nuevo == EstadoEnvio.INCIDENCIA and not (detalle and detalle.strip()):
        raise HTTPException(status_code=422, detail="Indique el motivo de la incidencia")

    # Regla: el repartidor debe aceptar la asignacion antes de retirar el paquete
    if nuevo == EstadoEnvio.RETIRADO:
        asig = conn.execute("SELECT aceptada_en FROM asignaciones WHERE envio_id = %s AND activa",
                            (envio["id"],)).fetchone()
        if asig is None or asig["aceptada_en"] is None:
            raise HTTPException(status_code=409, detail="El repartidor debe aceptar la asignacion antes de retirar")

    envio = conn.execute(
        "UPDATE envios SET estado = %s, actualizado_en = now() WHERE id = %s RETURNING *",
        (nuevo.value, envio["id"]),
    ).fetchone()
    conn.execute(
        """INSERT INTO eventos_envio (evento_id, envio_id, estado_anterior, estado_nuevo, actor, detalle)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (evento_id, envio["id"], actual.value, nuevo.value, actor, detalle),
    )
    if nuevo in LIBERAN_CAPACIDAD:   # el repartidor recupera cupo
        conn.execute("UPDATE asignaciones SET activa = FALSE WHERE envio_id = %s AND activa", (envio["id"],))
    conn.execute("INSERT INTO outbox (envio_id) VALUES (%s)", (envio["id"],))
    return envio, False

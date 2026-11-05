"""
routers/envios.py - Endpoints de envios.

  POST  /envios                   crea un envio (devuelve el codigo unico = comprobante)
  GET   /envios                   lista desde PostgreSQL con filtros (estado, zona_id)
  GET   /envios/{codigo}          envio + linea de tiempo + asignacion activa
  PATCH /envios/{codigo}/estado   cambio de estado validado por la maquina de estados

Regla de oro: cada escritura hace 3 cosas en UNA transaccion de PostgreSQL:
   1) actualiza el estado actual   2) agrega un evento al historial   3) agrega un aviso a la outbox
Asi estado e historial NUNCA se contradicen.
"""
import secrets
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.domain.estados import EstadoEnvio
from app.repositories import pg
from app.seguridad import PERMISOS_ESTADO, ROLES, requiere_rol
from app.services import cambiar_estado_tx

router = APIRouter(prefix="/envios", tags=["envios"])


# Pydantic valida los datos de entrada; si algo no cumple, FastAPI responde 422 solo.
class SolicitudEnvio(BaseModel):
    remitente: str = Field(min_length=2, max_length=100)
    destinatario: str = Field(min_length=2, max_length=100)
    origen: str = Field(min_length=2, max_length=200)
    destino: str = Field(min_length=2, max_length=200)
    tipo_servicio: str = Field(min_length=2, max_length=40)   # debe existir y estar activo (tabla tipos_servicio)
    zona_id: int = Field(gt=0)


class CambioEstado(BaseModel):
    nuevo_estado: EstadoEnvio
    actor: str = Field(min_length=2, max_length=100)   # quien lo hace (auditoria)
    evento_id: UUID                                    # lo genera el cliente: permite reintentar sin duplicar
    detalle: str | None = Field(default=None, max_length=300)   # motivo (obligatorio si es una incidencia)


def _generar_codigo() -> str:
    """Ej: ENV-9F3A1C7B. La unicidad REAL la garantiza el UNIQUE de la base de datos."""
    return "ENV-" + secrets.token_hex(4).upper()


@router.post("", status_code=201, dependencies=[Depends(requiere_rol(*ROLES))])
def crear_envio(datos: SolicitudEnvio):
    """Crea un envio en estado 'creado' y registra su primer evento."""
    try:
        with pg.conectar() as conn:   # transaccion: COMMIT al salir sin errores, ROLLBACK si hay excepcion
            tipo = conn.execute("SELECT activo FROM tipos_servicio WHERE nombre = %s", (datos.tipo_servicio,)).fetchone()
            if tipo is None or not tipo["activo"]:
                raise HTTPException(status_code=422, detail="El tipo de servicio no existe o esta desactivado")
            envio = conn.execute(
                """INSERT INTO envios (codigo, remitente, destinatario, origen, destino, tipo_servicio, zona_id)
                   VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *""",
                (_generar_codigo(), datos.remitente, datos.destinatario, datos.origen,
                 datos.destino, datos.tipo_servicio, datos.zona_id),
            ).fetchone()
            conn.execute(
                """INSERT INTO eventos_envio (evento_id, envio_id, estado_anterior, estado_nuevo, actor)
                   VALUES (gen_random_uuid(), %s, NULL, 'creado', 'cliente')""",
                (envio["id"],),
            )
            conn.execute("INSERT INTO outbox (envio_id) VALUES (%s)", (envio["id"],))
    except psycopg.errors.ForeignKeyViolation:
        raise HTTPException(status_code=422, detail="La zona indicada no existe")
    return envio


@router.get("")
def listar_envios(estado: EstadoEnvio | None = None, zona_id: int | None = None, limite: int = 100):
    """Lista envios desde PostgreSQL (fuente oficial). Incluye la asignacion activa, si existe.
    Ejemplo: GET /envios?estado=creado -> pendientes de asignar."""
    limite = max(1, min(limite, 500))
    condiciones, params = [], []
    if estado:
        condiciones.append("e.estado = %s"); params.append(estado.value)
    if zona_id:
        condiciones.append("e.zona_id = %s"); params.append(zona_id)
    where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""
    with pg.conectar() as conn:
        # Siempre con parametros (%s) -> sin riesgo de inyeccion SQL
        return conn.execute(
            f"""SELECT e.*, z.nombre AS zona, a.id AS asignacion_id, a.repartidor_id, r.nombre AS repartidor
                FROM envios e
                JOIN zonas z ON z.id = e.zona_id
                LEFT JOIN asignaciones a ON a.envio_id = e.id AND a.activa
                LEFT JOIN repartidores r ON r.id = a.repartidor_id
                {where} ORDER BY e.creado_en DESC LIMIT %s""",
            (*params, limite),
        ).fetchall()


@router.get("/{codigo}")
def consultar_envio(codigo: str):
    """Envio + linea de tiempo ordenada + asignacion activa + chequeo de consistencia."""
    with pg.conectar() as conn:
        envio = conn.execute(
            "SELECT e.*, z.nombre AS zona FROM envios e JOIN zonas z ON z.id = e.zona_id WHERE e.codigo = %s",
            (codigo,),
        ).fetchone()
        if envio is None:
            raise HTTPException(status_code=404, detail="Envio no encontrado")
        eventos = conn.execute(
            """SELECT evento_id, estado_anterior, estado_nuevo, actor, detalle, fecha
               FROM eventos_envio WHERE envio_id = %s ORDER BY fecha""",
            (envio["id"],),
        ).fetchall()
        asignacion = conn.execute(
            """SELECT a.id, a.repartidor_id, r.nombre AS repartidor, a.creada_en, a.aceptada_en
               FROM asignaciones a JOIN repartidores r ON r.id = a.repartidor_id
               WHERE a.envio_id = %s AND a.activa""",
            (envio["id"],),
        ).fetchone()
    # El estado actual debe coincidir con el ultimo evento del historial
    consistente = bool(eventos) and eventos[-1]["estado_nuevo"] == envio["estado"]
    return {"envio": envio, "eventos": eventos, "asignacion": asignacion, "consistente": consistente}


@router.patch("/{codigo}/estado")
def cambiar_estado(codigo: str, datos: CambioEstado, rol: str = Depends(requiere_rol(*ROLES))):
    """200 cambio aplicado (o reintento idempotente) | 403 rol sin permiso | 404 no existe
    409 transicion invalida | 422 falta el motivo de la incidencia."""
    if rol not in PERMISOS_ESTADO[datos.nuevo_estado.value]:
        raise HTTPException(status_code=403, detail=f"El rol '{rol}' no puede llevar un envio a '{datos.nuevo_estado.value}'")
    with pg.conectar() as conn:
        envio, repetido = cambiar_estado_tx(conn, codigo, datos.nuevo_estado, datos.actor, datos.evento_id, datos.detalle)
    return {"envio": envio, "repetido": repetido}

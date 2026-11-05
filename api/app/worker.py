"""
worker.py - Sincronizador (patron OUTBOX): PostgreSQL -> MongoDB.

Corre en su propio contenedor, en un bucle infinito:
  1. Lee de la tabla 'outbox' los avisos pendientes (procesado = FALSE).
  2. Para cada envio avisado, lee su estado ACTUAL en Postgres y lo copia
     (upsert) a la coleccion 'envios_busqueda' de Mongo.
  3. Marca el aviso como procesado.

Por que es seguro:
  - Si Mongo esta caido, el paso 2 falla, la transaccion se revierte y los avisos
    siguen pendientes: se reintenta en el siguiente ciclo. La API sigue operando.
  - Es IDEMPOTENTE: copiar el mismo envio dos veces deja el mismo resultado.
  - Se usa el estado actual de Postgres (no un dato viejo), asi que la proyeccion converge.
  - FOR UPDATE SKIP LOCKED: si hubiera 2 workers, no se pisan.

Ejecucion: python -m app.worker
"""
import logging
import time

from app.config import settings
from app.repositories import mongo, pg

logging.basicConfig(level=logging.INFO, format="%(asctime)s [worker] %(message)s")
log = logging.getLogger("worker")

TAMANO_LOTE = 50  # maximo de avisos que se procesan por ciclo


def procesar_lote() -> int:
    """Procesa hasta TAMANO_LOTE avisos pendientes. Devuelve cuantos proceso."""
    with pg.conectar() as conn:  # transaccion: todo el lote se confirma o se revierte junto
        pendientes = conn.execute(
            """SELECT id, envio_id FROM outbox
               WHERE NOT procesado ORDER BY id LIMIT %s
               FOR UPDATE SKIP LOCKED""",
            (TAMANO_LOTE,),
        ).fetchall()
        if not pendientes:
            return 0

        coleccion = mongo.obtener_db()["envios_busqueda"]
        for aviso in pendientes:
            envio = conn.execute(
                """SELECT e.codigo, e.remitente, e.destinatario, e.origen, e.destino,
                          e.tipo_servicio, e.estado, e.creado_en, e.actualizado_en,
                          z.nombre AS zona
                   FROM envios e JOIN zonas z ON z.id = e.zona_id
                   WHERE e.id = %s""",
                (aviso["envio_id"],),
            ).fetchone()

            # replace_one con upsert=True: si el documento existe lo reemplaza, si no lo crea.
            # Se usa el codigo del envio como _id para no duplicar.
            coleccion.replace_one({"_id": envio["codigo"]}, {"_id": envio["codigo"], **envio}, upsert=True)

            conn.execute(
                "UPDATE outbox SET procesado = TRUE, procesado_en = now() WHERE id = %s",
                (aviso["id"],),
            )
        return len(pendientes)


def main() -> None:
    log.info("Worker iniciado (intervalo: %ss)", settings.worker_intervalo)
    while True:
        try:
            n = procesar_lote()
            if n:
                log.info("Sincronizados %d envios hacia Mongo", n)
        except Exception as exc:
            # Cualquier fallo (Mongo caido, Postgres reiniciando...) NO detiene el worker:
            # se registra y se reintenta en el siguiente ciclo.
            log.warning("Fallo de sincronizacion, se reintentara: %s", exc)
        time.sleep(settings.worker_intervalo)


if __name__ == "__main__":
    main()

"""
repositories/pg.py - Conexion a PostgreSQL.

Uso tipico en el resto del codigo:

    with conectar() as conn:
        conn.execute("INSERT ...")
        conn.execute("UPDATE ...")
    # Al salir del "with" sin errores  -> COMMIT (se guardan TODOS los cambios)
    # Si ocurre una excepcion adentro  -> ROLLBACK (no se guarda NADA)

Eso es una TRANSACCION: o se hacen todas las operaciones o ninguna.
"""
import psycopg
from psycopg.rows import dict_row

from app.config import settings


def conectar() -> psycopg.Connection:
    """Abre una conexion nueva. dict_row hace que cada fila sea un diccionario
    (fila["codigo"]) en vez de una tupla (fila[0])."""
    return psycopg.connect(settings.pg_dsn, row_factory=dict_row)

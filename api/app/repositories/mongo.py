"""
repositories/mongo.py - Conexion a MongoDB.

Colecciones:
  - envios_busqueda : proyeccion para busquedas (la escribe el worker)
  - evidencias      : prueba de entrega (la escribira la API)
"""
from pymongo import MongoClient
from pymongo.database import Database

from app.config import settings

# Un solo cliente reutilizable (pymongo maneja su propio "pool" de conexiones).
# serverSelectionTimeoutMS=2000: si Mongo esta caido, falla en 2 s en lugar de colgarse.
_cliente = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=2000)


def obtener_db() -> Database:
    """Devuelve la base de datos 'mensajeria'."""
    return _cliente[settings.mongo_db]


def ping() -> None:
    """Lanza excepcion si Mongo no responde (la usa /health)."""
    _cliente.admin.command("ping")

"""
config.py - Configuracion de la aplicacion.

Lee las variables de entorno (las define docker-compose.yml a partir del archivo .env).
Asi NINGUNA contrasena queda escrita en el codigo.
"""
import os
from dataclasses import dataclass


@dataclass(frozen=True)  # frozen=True: los valores no se pueden modificar despues de creados
class Settings:
    # os.getenv("NOMBRE", "valor_por_defecto") lee una variable de entorno
    pg_host: str = os.getenv("PG_HOST", "localhost")
    pg_db: str = os.getenv("POSTGRES_DB", "mensajeria")
    pg_user: str = os.getenv("POSTGRES_USER", "")
    pg_password: str = os.getenv("POSTGRES_PASSWORD", "")

    mongo_host: str = os.getenv("MONGO_HOST", "localhost")
    mongo_user: str = os.getenv("MONGO_INITDB_ROOT_USERNAME", "")
    mongo_password: str = os.getenv("MONGO_INITDB_ROOT_PASSWORD", "")
    mongo_db: str = "mensajeria"

    redis_host: str = os.getenv("REDIS_HOST", "localhost")
    redis_password: str = os.getenv("REDIS_PASSWORD", "")

    # Segundos que dura la ultima posicion de un repartidor en Redis (lo fija el servidor, no el navegador)
    ttl_posicion: int = int(os.getenv("TTL_POSICION_SEGUNDOS", "60"))

    worker_intervalo: float = float(os.getenv("WORKER_INTERVALO_SEGUNDOS", "2"))

    @property
    def pg_dsn(self) -> str:
        """Cadena de conexion a PostgreSQL."""
        return (f"host={self.pg_host} dbname={self.pg_db} "
                f"user={self.pg_user} password={self.pg_password} connect_timeout=3")

    @property
    def mongo_uri(self) -> str:
        """URI de conexion a MongoDB (authSource=admin porque el usuario root vive en 'admin')."""
        return (f"mongodb://{self.mongo_user}:{self.mongo_password}"
                f"@{self.mongo_host}:27017/?authSource=admin")


# Objeto unico que importan los demas modulos: from app.config import settings
settings = Settings()

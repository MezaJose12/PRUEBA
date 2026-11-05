"""
repositories/redis_repo.py - Conexion a Redis (estado temporal).

Idea clave: los datos de Redis EXPIRAN solos (TTL). Ejemplo para la ultima posicion
de un repartidor (se implementara en el paso 6):

    r.set("repartidor:1:posicion", "-0.18,-78.47", ex=60)   # desaparece en 60 s

Si la clave ya no existe, significa "dato no vigente".
"""
import redis

from app.config import settings

# decode_responses=True: devuelve texto (str) en lugar de bytes
cliente = redis.Redis(
    host=settings.redis_host,
    password=settings.redis_password,
    decode_responses=True,
    socket_connect_timeout=2,
)

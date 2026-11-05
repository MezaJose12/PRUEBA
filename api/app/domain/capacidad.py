"""
domain/capacidad.py - Regla de capacidad del repartidor (logica de negocio pura).

OJO: esta funcion solo expresa la REGLA. Para que sea correcta con peticiones simultaneas,
el router de despacho bloquea la fila del repartidor en PostgreSQL (SELECT ... FOR UPDATE)
antes de contar su carga. Sin ese bloqueo, dos peticiones podrian leer "carga = 0" a la vez
y ambas asignarse (condicion de carrera).
"""


def puede_recibir(carga_actual: int, capacidad_max: int) -> bool:
    """True si el repartidor aun tiene cupo. carga_actual = envios activos asignados."""
    return carga_actual < capacidad_max

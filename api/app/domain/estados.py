"""
domain/estados.py - Maquina de estados del envio.

Define QUE estados existen y A CUALES se puede pasar desde cada uno.
Esta logica es de NEGOCIO: no depende de ninguna base de datos ni de FastAPI,
por eso vive en "domain" y es facil de probar.

Diagrama:
    creado -> asignado -> retirado -> en_transito -> entregado
       |         |                       |
    cancelado  creado (reasignacion)   incidencia -> en_transito | devuelto
"""
from enum import Enum


class EstadoEnvio(str, Enum):
    """Estados posibles. Al heredar de 'str', cada estado se comporta como texto
    (EstadoEnvio.CREADO == "creado"), lo que facilita guardarlo en la base de datos."""
    CREADO = "creado"
    ASIGNADO = "asignado"
    RETIRADO = "retirado"
    EN_TRANSITO = "en_transito"
    ENTREGADO = "entregado"
    INCIDENCIA = "incidencia"
    CANCELADO = "cancelado"
    DEVUELTO = "devuelto"

    def puede_pasar_a(self, destino: "EstadoEnvio") -> bool:
        """True si la transicion self -> destino esta permitida."""
        return destino in TRANSICIONES[self]


# Tabla de transiciones validas: {estado_actual: {estados a los que puede ir}}
# Los estados finales (entregado, cancelado, devuelto) tienen conjunto vacio: no se sale de ellos.
TRANSICIONES: dict[EstadoEnvio, set[EstadoEnvio]] = {
    EstadoEnvio.CREADO:       {EstadoEnvio.ASIGNADO, EstadoEnvio.CANCELADO},
    EstadoEnvio.ASIGNADO:     {EstadoEnvio.RETIRADO, EstadoEnvio.CREADO, EstadoEnvio.CANCELADO},
    EstadoEnvio.RETIRADO:     {EstadoEnvio.EN_TRANSITO, EstadoEnvio.INCIDENCIA},
    EstadoEnvio.EN_TRANSITO:  {EstadoEnvio.ENTREGADO, EstadoEnvio.INCIDENCIA},
    EstadoEnvio.INCIDENCIA:   {EstadoEnvio.EN_TRANSITO, EstadoEnvio.DEVUELTO},
    EstadoEnvio.ENTREGADO:    set(),
    EstadoEnvio.CANCELADO:    set(),
    EstadoEnvio.DEVUELTO:     set(),
}


# Estados que LIBERAN la capacidad del repartidor: al entrar en cualquiera de ellos,
# la asignacion activa del envio se cierra (activa = FALSE).
#   - entregado / cancelado / devuelto: el envio termino.
#   - creado: el envio volvio a la cola (reasignacion) antes del retiro.
LIBERAN_CAPACIDAD: set[EstadoEnvio] = {
    EstadoEnvio.ENTREGADO, EstadoEnvio.CANCELADO, EstadoEnvio.DEVUELTO, EstadoEnvio.CREADO,
}

"""
seguridad.py - Autorizacion SIMPLE por rol (solo para el laboratorio).

El navegador envia el encabezado  X-Rol: cliente | operador | repartidor | administrador
y la API decide si ese rol puede usar el endpoint.

LIMITACION (documentarla en la defensa): cualquiera puede escribir cualquier X-Rol, asi que
esto NO es autenticacion real. Mejora futura: login + JWT firmado. Lo importante aqui es que
la API (y no el navegador) es quien valida permisos, estados y capacidades.
"""
from fastapi import Header, HTTPException

ROLES = {"cliente", "operador", "repartidor", "administrador"}


def requiere_rol(*permitidos: str):
    """Crea una dependencia de FastAPI. Uso:
        @router.post("/x", dependencies=[Depends(requiere_rol("operador", "administrador"))])
    """
    def dependencia(x_rol: str | None = Header(default=None)) -> str:
        if x_rol is None:
            raise HTTPException(status_code=401, detail="Falta el encabezado X-Rol")
        if x_rol not in ROLES:
            raise HTTPException(status_code=403, detail=f"Rol desconocido: {x_rol}")
        if x_rol not in permitidos:
            raise HTTPException(status_code=403, detail=f"El rol '{x_rol}' no puede realizar esta accion")
        return x_rol
    return dependencia


# Quien puede llevar un envio A CADA ESTADO mediante PATCH /envios/{codigo}/estado.
# ('asignado' y 'entregado' tienen su propio endpoint; aqui no se usan.)
_OPER = {"repartidor", "operador", "administrador"}
PERMISOS_ESTADO: dict[str, set[str]] = {
    "cancelado":   {"cliente", "operador", "administrador"},
    "creado":      {"operador", "administrador"},
    "retirado":    _OPER, "en_transito": _OPER, "incidencia": _OPER, "devuelto": _OPER,
    "asignado":    {"operador", "administrador"},
    "entregado":   {"repartidor", "administrador"},
}

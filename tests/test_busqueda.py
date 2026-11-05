"""test_busqueda.py - [INTEGRACION] La proyeccion en Mongo se actualiza (flujo 5): consistencia eventual."""
from conftest import esperar, nuevo_uuid


def _en_busqueda(cliente, codigo, estado=None):
    def _f():
        r = cliente.get("/buscar", params={"codigo": codigo}).json()["resultados"]
        return r and (estado is None or r[0]["estado"] == estado)
    return _f


def test_envio_nuevo_aparece_en_busqueda(cliente, crear_envio):
    codigo = crear_envio()
    assert esperar(_en_busqueda(cliente, codigo), segundos=20), "El worker no sincronizo a tiempo"


def test_cambio_de_estado_se_refleja_en_busqueda(cliente, crear_envio):
    codigo = crear_envio()
    cliente.patch(f"/envios/{codigo}/estado",
                  json={"nuevo_estado": "cancelado", "actor": "operador", "evento_id": nuevo_uuid()})
    assert esperar(_en_busqueda(cliente, codigo, "cancelado"), segundos=20)

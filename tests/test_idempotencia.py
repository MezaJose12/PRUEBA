"""
test_idempotencia.py - [INTEGRACION] Un reintento con el mismo evento_id no duplica el historial.
Requiere la API levantada.
"""
from conftest import nuevo_uuid


def test_reintento_no_duplica_evento(cliente, crear_envio):
    codigo = crear_envio()
    cuerpo = {"nuevo_estado": "cancelado", "actor": "operador", "evento_id": nuevo_uuid()}

    r1 = cliente.patch(f"/envios/{codigo}/estado", json=cuerpo)
    r2 = cliente.patch(f"/envios/{codigo}/estado", json=cuerpo)   # reintento identico

    assert r1.status_code == 200 and r1.json()["repetido"] is False
    assert r2.status_code == 200 and r2.json()["repetido"] is True

    eventos = cliente.get(f"/envios/{codigo}").json()["eventos"]
    assert [e["estado_nuevo"] for e in eventos].count("cancelado") == 1


def test_transicion_invalida_devuelve_409(cliente, crear_envio):
    codigo = crear_envio()
    r = cliente.patch(f"/envios/{codigo}/estado",
                      json={"nuevo_estado": "entregado", "actor": "operador", "evento_id": nuevo_uuid()})
    assert r.status_code == 409

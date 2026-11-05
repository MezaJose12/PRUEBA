"""test_evidencias.py - [INTEGRACION] Flujo 4: entrega con evidencia, sin contradicciones."""
from conftest import nuevo_uuid


def test_entrega_con_evidencia_y_reintento_idempotente(cliente, crear_envio, llevar_a_transito, entregar):
    codigo = crear_envio()
    llevar_a_transito(codigo)
    ev_id, evento_id = nuevo_uuid(), nuevo_uuid()

    r1 = entregar(codigo, ev_id, evento_id)
    r2 = entregar(codigo, ev_id, evento_id)            # reintento identico
    assert r1.status_code == 201 and r1.json()["repetido"] is False
    assert r2.status_code == 200 and r2.json()["repetido"] is True

    det = cliente.get(f"/envios/{codigo}").json()
    assert det["envio"]["estado"] == "entregado"
    assert det["consistente"] is True                              # estado == ultimo evento
    assert [e["estado_nuevo"] for e in det["eventos"]].count("entregado") == 1
    ev = cliente.get(f"/envios/{codigo}/evidencia")
    assert ev.status_code == 200 and ev.json()["receptor"] == "Receptor Ficticio"


def test_no_se_entrega_un_envio_creado(cliente, crear_envio, entregar):
    assert entregar(crear_envio()).status_code == 409


def test_patch_no_puede_marcar_entregado(cliente, crear_envio, llevar_a_transito, entregar):
    codigo = crear_envio()
    llevar_a_transito(codigo)
    r = cliente.patch(f"/envios/{codigo}/estado",
                      json={"nuevo_estado": "entregado", "actor": "x", "evento_id": nuevo_uuid()})
    assert r.status_code == 409                                    # exige evidencia
    assert entregar(codigo).status_code == 201                     # limpieza: libera el cupo

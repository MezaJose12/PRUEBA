"""
test_reglas.py - [INTEGRACION] Reglas de negocio: aceptacion, incidencias, roles, tipos de servicio y semilla.
"""
import uuid

import httpx
from conftest import API_URL, nuevo_uuid


def _asignar(cliente, codigo, repartidor=1):
    r = cliente.post("/asignaciones", json={"codigo_envio": codigo, "repartidor_id": repartidor,
                                            "actor": "operador", "evento_id": nuevo_uuid()})
    assert r.status_code == 201, r.text
    return r.json()["asignacion"]["id"]


def _carga(cliente, repartidor=1):
    return next(r for r in cliente.get("/repartidores").json() if r["id"] == repartidor)["carga_actual"]


def _accion(cliente, asig_id, accion):
    return cliente.patch(f"/asignaciones/{asig_id}/{accion}", json={"actor": "repartidor", "evento_id": nuevo_uuid()})


def _estado(cliente, codigo, nuevo, detalle=None, actor="repartidor"):
    return cliente.patch(f"/envios/{codigo}/estado", json={"nuevo_estado": nuevo, "actor": actor,
                                                           "evento_id": nuevo_uuid(), "detalle": detalle})


# ---- Aceptar / rechazar asignacion ----
def test_no_se_retira_sin_aceptar(cliente, crear_envio):
    codigo = crear_envio()
    asig = _asignar(cliente, codigo)
    assert _estado(cliente, codigo, "retirado").status_code == 409
    cliente.patch(f"/asignaciones/{asig}/liberar", json={"actor": "operador", "evento_id": nuevo_uuid()})


def test_aceptar_queda_en_el_historial_y_permite_retirar(cliente, crear_envio, entregar, llevar_a_transito):
    codigo = crear_envio()
    llevar_a_transito(codigo)                       # incluye aceptar
    detalles = [e["detalle"] for e in cliente.get(f"/envios/{codigo}").json()["eventos"]]
    assert "Asignacion aceptada por el repartidor" in detalles
    assert entregar(codigo).status_code == 201     # limpieza


def test_rechazar_devuelve_el_envio_y_libera_cupo(cliente, crear_envio):
    antes = _carga(cliente)
    codigo = crear_envio()
    asig = _asignar(cliente, codigo)
    assert _carga(cliente) == antes + 1
    assert _accion(cliente, asig, "rechazar").status_code == 200
    assert cliente.get(f"/envios/{codigo}").json()["envio"]["estado"] == "creado"
    assert _carga(cliente) == antes


def test_no_se_puede_rechazar_despues_de_aceptar(cliente, crear_envio):
    codigo = crear_envio()
    asig = _asignar(cliente, codigo)
    assert _accion(cliente, asig, "aceptar").status_code == 200
    assert _accion(cliente, asig, "rechazar").status_code == 409
    cliente.patch(f"/asignaciones/{asig}/liberar", json={"actor": "operador", "evento_id": nuevo_uuid()})


# ---- Incidencias ----
def test_incidencia_exige_motivo_y_la_resuelve_el_operador(cliente, crear_envio, llevar_a_transito, entregar):
    codigo = crear_envio()
    llevar_a_transito(codigo)
    assert _estado(cliente, codigo, "incidencia").status_code == 422             # sin motivo
    assert _estado(cliente, codigo, "incidencia", "Destinatario ausente").status_code == 200
    lista = cliente.get("/envios", params={"estado": "incidencia"}).json()
    assert next(e for e in lista if e["codigo"] == codigo)["ultimo_detalle"] == "Destinatario ausente"
    assert _estado(cliente, codigo, "en_transito", "Resuelta", actor="operador").status_code == 200
    assert entregar(codigo).status_code == 201                                   # limpieza


# ---- Roles ----
def _con_rol(rol):
    return httpx.Client(base_url=API_URL, headers={"X-Rol": rol}, timeout=15)


def test_cliente_cancela_pero_no_retira(cliente, crear_envio):
    codigo = crear_envio()
    with _con_rol("cliente") as c:
        assert _estado(c, codigo, "retirado").status_code == 403
        assert _estado(c, codigo, "cancelado", actor="cliente").status_code == 200


def test_repartidor_no_puede_cancelar_ni_asignar(cliente, crear_envio):
    codigo = crear_envio()
    with _con_rol("repartidor") as c:
        assert _estado(c, codigo, "cancelado").status_code == 403
        r = c.post("/asignaciones", json={"codigo_envio": codigo, "repartidor_id": 1, "actor": "x", "evento_id": nuevo_uuid()})
        assert r.status_code == 403


def test_solo_administrador_gestiona_catalogos():
    with _con_rol("operador") as c:
        assert c.post("/zonas", json={"nombre": "Zona " + uuid.uuid4().hex[:5]}).status_code == 403
        assert c.post("/tipos-servicio", json={"nombre": "x" + uuid.uuid4().hex[:5]}).status_code == 403


# ---- Tipos de servicio administrables ----
def test_tipo_de_servicio_nuevo_se_puede_usar_y_desactivar(cliente):
    nombre = "tipo-" + uuid.uuid4().hex[:6]
    assert cliente.post("/tipos-servicio", json={"nombre": nombre}).status_code == 201
    datos = {"remitente": "Ana Ficticia", "destinatario": "Luis Ficticio", "origen": "Calle A 1",
             "destino": "Calle B 2", "tipo_servicio": nombre, "zona_id": 1}
    assert cliente.post("/envios", json=datos).status_code == 201

    tipo = next(t for t in cliente.get("/tipos-servicio").json() if t["nombre"] == nombre)
    assert cliente.patch(f"/tipos-servicio/{tipo['id']}", json={"activo": False}).status_code == 200
    assert cliente.post("/envios", json=datos).status_code == 422                # desactivado
    assert cliente.post("/envios", json={**datos, "tipo_servicio": "no-existe"}).status_code == 422


# ---- Datos semilla ----
def test_envios_semilla_son_coherentes(cliente):
    for n in range(1, 9):
        d = cliente.get(f"/envios/ENV-DEMO000{n}")
        assert d.status_code == 200, "Falta la semilla: ejecute docker compose down -v && docker compose up --build -d"
        assert d.json()["consistente"] is True
    assert cliente.get("/envios/ENV-DEMO0006/evidencia").status_code == 200

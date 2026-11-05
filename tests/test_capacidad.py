"""
test_capacidad.py - [INTEGRACION] Control de capacidad y concurrencia (prueba 3 de la defensa).
El repartidor 3 de los datos semilla tiene capacidad_max = 1.
Si una prueba falla a mitad y deja cupo ocupado:  docker compose down -v && docker compose up -d
"""
from concurrent.futures import ThreadPoolExecutor

import httpx
from conftest import API_URL, CABECERAS, REPARTIDOR_CAP_1, nuevo_uuid


def _asignar(codigo):
    with httpx.Client(base_url=API_URL, timeout=20, headers=CABECERAS) as c:   # un cliente por hilo
        return c.post("/asignaciones", json={"codigo_envio": codigo, "repartidor_id": REPARTIDOR_CAP_1,
                                             "actor": "operador", "evento_id": nuevo_uuid()})


def _liberar(cliente, resp):
    cliente.patch(f"/asignaciones/{resp.json()['asignacion']['id']}/liberar",
                  json={"actor": "operador", "evento_id": nuevo_uuid()})


def test_dos_asignaciones_simultaneas_solo_una_gana(cliente, crear_envio):
    a, b = crear_envio(), crear_envio()
    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(_asignar, [a, b]))
    assert sorted(r.status_code for r in resultados) == [201, 409], [r.text for r in resultados]
    _liberar(cliente, next(r for r in resultados if r.status_code == 201))


def test_entregar_libera_capacidad(cliente, crear_envio, llevar_a_transito, entregar):
    codigo = crear_envio()
    llevar_a_transito(codigo, REPARTIDOR_CAP_1)
    assert entregar(codigo).status_code == 201
    otro = _asignar(crear_envio())            # el cupo se libero al entregar
    assert otro.status_code == 201
    _liberar(cliente, otro)


def test_no_se_puede_asignar_por_patch(cliente, crear_envio):
    r = cliente.patch(f"/envios/{crear_envio()}/estado",
                      json={"nuevo_estado": "asignado", "actor": "operador", "evento_id": nuevo_uuid()})
    assert r.status_code == 409


def test_rol_cliente_no_puede_asignar(crear_envio):
    codigo = crear_envio()
    with httpx.Client(base_url=API_URL, headers={"X-Rol": "cliente"}) as c:
        r = c.post("/asignaciones", json={"codigo_envio": codigo, "repartidor_id": 1,
                                          "actor": "x", "evento_id": nuevo_uuid()})
    assert r.status_code == 403

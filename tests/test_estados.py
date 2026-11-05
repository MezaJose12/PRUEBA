"""
test_estados.py - Pruebas UNITARIAS de la maquina de estados y la regla de capacidad.
No necesitan Docker ni base de datos:  pytest tests/test_estados.py
"""
from app.domain.capacidad import puede_recibir
from app.domain.estados import LIBERAN_CAPACIDAD, TRANSICIONES, EstadoEnvio as E


def test_secuencia_valida():
    ruta = [E.CREADO, E.ASIGNADO, E.RETIRADO, E.EN_TRANSITO, E.ENTREGADO]
    for a, b in zip(ruta, ruta[1:]):
        assert a.puede_pasar_a(b)


def test_creado_a_entregado_es_invalido():
    assert not E.CREADO.puede_pasar_a(E.ENTREGADO)


def test_estados_finales_no_tienen_salida():
    for final in (E.ENTREGADO, E.CANCELADO, E.DEVUELTO):
        assert TRANSICIONES[final] == set()


def test_incidencia_puede_continuar_o_devolver():
    assert E.INCIDENCIA.puede_pasar_a(E.EN_TRANSITO)
    assert E.INCIDENCIA.puede_pasar_a(E.DEVUELTO)


def test_todos_los_estados_tienen_regla():
    assert set(TRANSICIONES) == set(E)


def test_estados_que_liberan_capacidad():
    assert E.ENTREGADO in LIBERAN_CAPACIDAD and E.RETIRADO not in LIBERAN_CAPACIDAD


def test_regla_de_capacidad():
    assert puede_recibir(0, 1)
    assert not puede_recibir(1, 1)
    assert puede_recibir(2, 3)

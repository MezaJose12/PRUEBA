"""
conftest.py - Configuracion comun de las pruebas.

Pruebas UNITARIAS (sin Docker):        pytest tests/test_estados.py
Pruebas de INTEGRACION (API activa):   docker compose up --build -d  &&  pytest tests/
Otra URL:                              API_URL=http://localhost:8000 pytest
"""
import os
import sys
import time
import uuid

import httpx
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))   # para importar "app"

API_URL = os.getenv("API_URL", "http://localhost:8000")
CABECERAS = {"X-Rol": "administrador"}      # rol simulado (ver api/app/seguridad.py)
REPARTIDOR_CAP_3 = 1                        # repartidor semilla con capacidad 3
REPARTIDOR_CAP_1 = 3                        # repartidor semilla con capacidad 1


def nuevo_uuid() -> str:
    return str(uuid.uuid4())


def esperar(condicion, segundos=30, cada=1.0):
    """Repite condicion() hasta que devuelva algo verdadero o se acabe el tiempo."""
    limite = time.time() + segundos
    while time.time() < limite:
        try:
            r = condicion()
            if r:
                return r
        except Exception:
            pass
        time.sleep(cada)
    return None


@pytest.fixture
def cliente():
    with httpx.Client(base_url=API_URL, timeout=15, headers=CABECERAS) as c:
        yield c


@pytest.fixture
def crear_envio(cliente):
    """Devuelve una funcion que crea un envio ficticio y retorna su codigo."""
    def _crear():
        r = cliente.post("/envios", json={
            "remitente": "Ana Ficticia", "destinatario": "Luis Ficticio",
            "origen": "Calle A 1", "destino": "Calle B 2", "tipo_servicio": "estandar", "zona_id": 1})
        assert r.status_code == 201, r.text
        return r.json()["codigo"]
    return _crear


@pytest.fixture
def llevar_a_transito(cliente):
    """Asigna (repartidor 1), el repartidor acepta y avanza el envio hasta 'en_transito'."""
    def _llevar(codigo, repartidor=REPARTIDOR_CAP_3):
        r = cliente.post("/asignaciones", json={"codigo_envio": codigo, "repartidor_id": repartidor,
                                                "actor": "operador", "evento_id": nuevo_uuid()})
        assert r.status_code == 201, r.text
        acept = cliente.patch(f"/asignaciones/{r.json()['asignacion']['id']}/aceptar",
                              json={"actor": "repartidor", "evento_id": nuevo_uuid()})
        assert acept.status_code == 200, acept.text
        for estado in ("retirado", "en_transito"):
            r = cliente.patch(f"/envios/{codigo}/estado",
                              json={"nuevo_estado": estado, "actor": "repartidor", "evento_id": nuevo_uuid()})
            assert r.status_code == 200, r.text
    return _llevar


@pytest.fixture
def entregar(cliente):
    def _entregar(codigo, evidencia_id=None, evento_id=None):
        return cliente.post(f"/envios/{codigo}/entrega", json={
            "receptor": "Receptor Ficticio", "observacion": "Entregado en porteria",
            "foto_url": "https://ejemplo.test/foto.jpg", "actor": "repartidor",
            "evidencia_id": evidencia_id or nuevo_uuid(), "evento_id": evento_id or nuevo_uuid()})
    return _entregar

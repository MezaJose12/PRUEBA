"""
test_sincronizacion.py - [INTEGRACION + DOCKER] Prueba 5: caida de Mongo y recuperacion.
Detiene el contenedor de Mongo, asi que debe ejecutarse desde la raiz del proyecto con Docker disponible.
"""
import shutil
import subprocess

import pytest
from conftest import esperar

RAIZ = __file__.rsplit("tests", 1)[0]
sin_docker = pytest.mark.skipif(shutil.which("docker") is None, reason="Docker no disponible")


def compose(*args):
    subprocess.run(["docker", "compose", *args], cwd=RAIZ, check=True, capture_output=True)


@sin_docker
def test_si_mongo_cae_el_registro_sigue_y_luego_se_sincroniza(cliente, crear_envio):
    compose("stop", "mongo")
    try:
        codigo = crear_envio()                                              # 1) se puede seguir creando
        assert cliente.get(f"/envios/{codigo}").status_code == 200          # 2) la fuente oficial responde
        assert cliente.get("/buscar", params={"codigo": codigo}).status_code == 503   # 3) busqueda no disponible
        assert cliente.get("/health").json()["estado"] == "degradado"
    finally:
        compose("start", "mongo")
    # 4) al volver Mongo, el worker se pone al dia solo (la outbox conservo el aviso)
    assert esperar(lambda: cliente.get("/buscar", params={"codigo": codigo}).json()["resultados"], segundos=90)


def test_reconstruir_proyeccion_desde_postgres(cliente, crear_envio):
    crear_envio()
    assert cliente.post("/sincronizacion/reconstruir").json()["avisos_encolados"] >= 1
    assert esperar(lambda: cliente.get("/sincronizacion/estado").json()["sincronizado"], segundos=60)

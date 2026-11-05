"""
test_fallos.py - [INTEGRACION + DOCKER] Pruebas 4 y 5: Redis efimero y persistencia tras reinicio.
Reinician contenedores; ejecutar desde la raiz del proyecto.
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
def test_redis_pierde_lo_efimero_pero_no_el_historial(cliente, crear_envio):
    codigo = crear_envio()
    assert cliente.put("/repartidores/1/posicion", json={"lat": -0.18, "lon": -78.47}).json()["vigente"] is True
    compose("restart", "redis")
    estado = esperar(lambda: cliente.get("/repartidores/1/posicion").status_code == 200 and
                     cliente.get("/repartidores/1/posicion").json(), segundos=30)
    assert estado and estado["vigente"] is False                              # lo efimero se perdio
    assert cliente.get(f"/envios/{codigo}").json()["eventos"]                 # el historial sigue


@sin_docker
def test_entrega_persiste_tras_reiniciar_todo(cliente, crear_envio, llevar_a_transito, entregar):
    codigo = crear_envio()
    llevar_a_transito(codigo)
    assert entregar(codigo).status_code == 201
    compose("restart", "postgres", "mongo", "redis", "api", "worker")
    assert esperar(lambda: cliente.get("/health").status_code == 200, segundos=90, cada=2)
    assert cliente.get(f"/envios/{codigo}").json()["envio"]["estado"] == "entregado"
    assert cliente.get(f"/envios/{codigo}/evidencia").status_code == 200


@sin_docker
def test_historial_es_append_only_a_nivel_de_base_de_datos():
    """Aunque alguien tenga acceso a la BD, el trigger impide editar o borrar eventos."""
    for sentencia in ("UPDATE eventos_envio SET actor = 'x'", "DELETE FROM eventos_envio", "TRUNCATE eventos_envio"):
        r = subprocess.run(["docker", "compose", "exec", "-T", "postgres", "sh", "-c",
                            f'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "{sentencia}"'],
                           cwd=RAIZ, capture_output=True, text=True)
        assert r.returncode != 0 and "append-only" in (r.stdout + r.stderr), sentencia

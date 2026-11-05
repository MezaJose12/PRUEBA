#!/usr/bin/env python3
"""
demo.py - Recorre los flujos 1 a 4 contra la API y muestra cada paso (ideal para grabar evidencias).
Sin dependencias externas. Uso:  python3 scripts/demo.py [http://localhost:8000]
"""
import json
import sys
import time
import urllib.error
import urllib.request
import uuid

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"


def llamar(metodo, ruta, cuerpo=None):
    req = urllib.request.Request(BASE + ruta, method=metodo,
                                 data=json.dumps(cuerpo).encode() if cuerpo else None,
                                 headers={"Content-Type": "application/json", "X-Rol": "administrador"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def paso(titulo, resultado):
    status, cuerpo = resultado
    resumen = cuerpo.get("detail") if isinstance(cuerpo, dict) and "detail" in cuerpo else "ok"
    print(f"[{status}] {titulo}: {resumen}")
    return cuerpo


def cambiar(codigo, estado, actor="repartidor", detalle=None):
    return llamar("PATCH", f"/envios/{codigo}/estado",
                  {"nuevo_estado": estado, "actor": actor, "evento_id": str(uuid.uuid4()), "detalle": detalle})


print("== Flujo 1: crear envio ==")
envio = paso("Crear envio", llamar("POST", "/envios", {
    "remitente": "Ana Ficticia", "destinatario": "Luis Ficticio", "origen": "Calle A 1",
    "destino": "Calle B 2", "tipo_servicio": "express", "zona_id": 1}))
codigo = envio["codigo"]
print("   codigo:", codigo)

print("\n== Maquina de estados ==")
paso("creado -> entregado (debe ser 409)", cambiar(codigo, "entregado"))

print("\n== Flujo 2: asignar con control de capacidad ==")
asig = paso("Asignar repartidor 1", llamar("POST", "/asignaciones", {
    "codigo_envio": codigo, "repartidor_id": 1, "actor": "operador", "evento_id": str(uuid.uuid4())}))
paso("Retirar SIN aceptar (debe ser 409)", cambiar(codigo, "retirado"))
paso("El repartidor acepta la asignacion", llamar("PATCH", f"/asignaciones/{asig['asignacion']['id']}/aceptar",
     {"actor": "repartidor-1", "evento_id": str(uuid.uuid4())}))

print("\n== Flujo 3: retiro, transito e incidencia ==")
paso("-> retirado", cambiar(codigo, "retirado"))
paso("-> en_transito", cambiar(codigo, "en_transito"))
paso("-> incidencia SIN motivo (debe ser 422)", cambiar(codigo, "incidencia"))
paso("-> incidencia con motivo", cambiar(codigo, "incidencia", detalle="Destinatario ausente"))
paso("Operador reanuda -> en_transito", cambiar(codigo, "en_transito", "operador", "Resuelta por el operador"))

print("\n== Flujo 4: entrega con evidencia ==")
ids = {"evidencia_id": str(uuid.uuid4()), "evento_id": str(uuid.uuid4())}
cuerpo = {"receptor": "Receptor Ficticio", "observacion": "Entregado en porteria",
          "foto_url": "https://ejemplo.test/foto.jpg", "actor": "repartidor", **ids}
paso("Entrega", llamar("POST", f"/envios/{codigo}/entrega", cuerpo))
paso("Reintento identico (200, repetido)", llamar("POST", f"/envios/{codigo}/entrega", cuerpo))

det = llamar("GET", f"/envios/{codigo}")[1]
print("\nHistorial:", " -> ".join(e["estado_nuevo"] for e in det["eventos"]))
print("Estado actual:", det["envio"]["estado"], "| coherente con historial:", det["consistente"])

print("\n== Flujo 5: proyeccion de busqueda (Mongo) ==")
for _ in range(15):
    r = llamar("GET", f"/buscar?codigo={codigo}")[1]
    if r["resultados"] and r["resultados"][0]["estado"] == "entregado":
        print("Visible en la busqueda con estado:", r["resultados"][0]["estado"]); break
    time.sleep(1)
else:
    print("La busqueda aun no refleja el ultimo estado (consistencia eventual / worker detenido)")

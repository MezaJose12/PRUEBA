"""
main.py - Punto de entrada de la API.

Crea la aplicacion FastAPI y "conecta" los routers (grupos de endpoints).
Documentacion interactiva automatica (OpenAPI): http://localhost:8000/docs
"""
from fastapi import FastAPI

from app.routers import admin, buscar, despacho, envios, evidencias, health, posiciones

app = FastAPI(
    title="Mensajeria urbana - API",
    description="Proyecto final: persistencia poliglota (PostgreSQL + MongoDB + Redis).",
    version="1.0.0",
)

app.include_router(health.router)       # GET /health
app.include_router(envios.router)       # /envios  (PostgreSQL)
app.include_router(despacho.router)     # /asignaciones, /repartidores  (PostgreSQL, control de capacidad)
app.include_router(evidencias.router)   # /envios/{codigo}/entrega|evidencia  (MongoDB + PostgreSQL)
app.include_router(posiciones.router)   # /repartidores/{id}/posicion  (Redis con TTL)
app.include_router(buscar.router)       # /buscar, /sincronizacion/*  (MongoDB proyeccion)
app.include_router(admin.router)        # /zonas, mantenimiento de repartidores

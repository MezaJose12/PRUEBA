#!/usr/bin/env bash
# Exporta la especificacion OpenAPI (entregable 5) con la API activa.
curl -s http://localhost:8000/openapi.json -o docs/openapi.json && echo "Guardado en docs/openapi.json"

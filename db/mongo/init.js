// =============================================================================
// init.js : indices de MongoDB (se ejecuta solo la primera vez que se crea el volumen)
//
// Colecciones:
//   envios_busqueda : PROYECCION derivada de PostgreSQL (la llena el worker).
//                     Si se pierde, se puede reconstruir desde Postgres.
//   evidencias      : prueba de entrega. Es dato OFICIAL (no se puede reconstruir).
// =============================================================================
db = db.getSiblingDB("mensajeria");

// Vista de busqueda: filtros por estado, zona, destinatario y fecha
db.envios_busqueda.createIndex({ estado: 1 });
db.envios_busqueda.createIndex({ zona: 1 });
db.envios_busqueda.createIndex({ destinatario: 1 });
db.envios_busqueda.createIndex({ creado_en: -1 });

// Evidencias: una sola evidencia por envio; evidencia_id evita duplicados por reintento
db.evidencias.createIndex({ evidencia_id: 1 }, { unique: true });
db.evidencias.createIndex({ codigo_envio: 1 });

// Evidencia de ejemplo para el envio entregado de la semilla (ENV-DEMO0006)
db.evidencias.insertOne({
  _id: "ENV-DEMO0006", evidencia_id: "00000000-0000-4000-8000-000000000006", codigo_envio: "ENV-DEMO0006",
  receptor: "Maria Ficticia", observacion: "Entregado en recepcion",
  foto_url: "https://ejemplo.test/fotos/demo0006.jpg", actor: "repartidor-2", registrada_en: new Date()
});

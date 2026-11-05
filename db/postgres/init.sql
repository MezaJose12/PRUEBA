-- =============================================================================
-- init.sql : esquema de PostgreSQL (fuente oficial de la verdad)
-- Se ejecuta automaticamente SOLO la primera vez que se crea el volumen.
-- Para volver a ejecutarlo hay que borrar el volumen: docker compose down -v
-- =============================================================================

-- Zonas de la ciudad (las mantiene el administrador)
CREATE TABLE zonas (
    id      SERIAL PRIMARY KEY,
    nombre  TEXT NOT NULL UNIQUE
);

-- Tipos de servicio (los mantiene el administrador). ON UPDATE CASCADE en envios:
-- si se renombra un tipo, los envios existentes lo siguen.
CREATE TABLE tipos_servicio (
    id      SERIAL PRIMARY KEY,
    nombre  TEXT NOT NULL UNIQUE,
    activo  BOOLEAN NOT NULL DEFAULT TRUE
);

-- Repartidores y su capacidad maxima de envios activos simultaneos
CREATE TABLE repartidores (
    id             SERIAL PRIMARY KEY,
    nombre         TEXT NOT NULL,
    capacidad_max  INT  NOT NULL CHECK (capacidad_max > 0),
    activo         BOOLEAN NOT NULL DEFAULT TRUE
);

-- Envios: guarda el ESTADO ACTUAL. El codigo es unico (lo ve el cliente).
CREATE TABLE envios (
    id             SERIAL PRIMARY KEY,
    codigo         TEXT NOT NULL UNIQUE,
    remitente      TEXT NOT NULL,
    destinatario   TEXT NOT NULL,
    origen         TEXT NOT NULL,
    destino        TEXT NOT NULL,
    tipo_servicio  TEXT NOT NULL REFERENCES tipos_servicio(nombre) ON UPDATE CASCADE,
    zona_id        INT  NOT NULL REFERENCES zonas(id),
    estado         TEXT NOT NULL DEFAULT 'creado'
                   CHECK (estado IN ('creado','asignado','retirado','en_transito',
                                     'entregado','incidencia','cancelado','devuelto')),
    creado_en      TIMESTAMPTZ NOT NULL DEFAULT now(),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Asignaciones: vinculo envio <-> repartidor.
-- El indice parcial garantiza UN SOLO vinculo activo por envio.
-- aceptada_en: el repartidor debe ACEPTAR la asignacion antes de poder retirar el paquete.
CREATE TABLE asignaciones (
    id            SERIAL PRIMARY KEY,
    envio_id      INT NOT NULL REFERENCES envios(id),
    repartidor_id INT NOT NULL REFERENCES repartidores(id),
    activa        BOOLEAN NOT NULL DEFAULT TRUE,
    aceptada_en   TIMESTAMPTZ,
    creada_en     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ux_asignacion_activa_por_envio
    ON asignaciones (envio_id) WHERE activa;

-- Historial de eventos: APPEND-ONLY (solo se inserta; un trigger impide UPDATE/DELETE/TRUNCATE).
-- evento_id lo genera el cliente y es UNICO -> idempotencia ante reintentos.
-- detalle: texto libre (motivo de incidencia, "asignacion aceptada", etc.)
CREATE TABLE eventos_envio (
    evento_id       UUID PRIMARY KEY,
    envio_id        INT  NOT NULL REFERENCES envios(id),
    estado_anterior TEXT,
    estado_nuevo    TEXT NOT NULL,
    actor           TEXT NOT NULL,
    detalle         TEXT,
    fecha           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_eventos_por_envio ON eventos_envio (envio_id, fecha);

-- Blindaje del historial: nadie (ni la API ni un error) puede editar o borrar eventos.
CREATE FUNCTION bloquear_modificacion_eventos() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'eventos_envio es append-only: operacion % no permitida', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_eventos_inmutables BEFORE UPDATE OR DELETE ON eventos_envio
    FOR EACH ROW EXECUTE FUNCTION bloquear_modificacion_eventos();
CREATE TRIGGER trg_eventos_sin_truncate BEFORE TRUNCATE ON eventos_envio
    FOR EACH STATEMENT EXECUTE FUNCTION bloquear_modificacion_eventos();

-- Outbox: cola de "avisos de cambio" para sincronizar con Mongo.
-- Se inserta en la MISMA transaccion que el cambio de datos.
CREATE TABLE outbox (
    id           BIGSERIAL PRIMARY KEY,
    envio_id     INT NOT NULL REFERENCES envios(id),
    procesado    BOOLEAN NOT NULL DEFAULT FALSE,
    creado_en    TIMESTAMPTZ NOT NULL DEFAULT now(),
    procesado_en TIMESTAMPTZ
);
CREATE INDEX ix_outbox_pendientes ON outbox (id) WHERE NOT procesado;

-- ------------------------- Datos semilla (ficticios) -------------------------
INSERT INTO zonas (nombre) VALUES ('Norte'), ('Centro'), ('Sur');
INSERT INTO tipos_servicio (nombre) VALUES ('estandar'), ('express');
INSERT INTO repartidores (nombre, capacidad_max) VALUES
    ('Repartidor Ficticio 1', 3),
    ('Repartidor Ficticio 2', 2),
    ('Repartidor Ficticio 3', 1);

-- Envios de ejemplo en distintos estados (cada uno con historial coherente).
-- Capacidad resultante: repartidor 1 = 2/3, repartidor 2 = 2/2 (lleno), repartidor 3 = 0/1.
CREATE FUNCTION _ev(p_codigo TEXT, p_ant TEXT, p_nuevo TEXT, p_actor TEXT, p_min INT, p_detalle TEXT DEFAULT NULL)
RETURNS void AS $$
    INSERT INTO eventos_envio (evento_id, envio_id, estado_anterior, estado_nuevo, actor, detalle, fecha)
    SELECT gen_random_uuid(), id, p_ant, p_nuevo, p_actor, p_detalle, now() - make_interval(mins => p_min)
    FROM envios WHERE codigo = p_codigo;
$$ LANGUAGE sql;

INSERT INTO envios (codigo, remitente, destinatario, origen, destino, tipo_servicio, zona_id, estado, creado_en) VALUES
 ('ENV-DEMO0001','Tienda Ficticia A','Maria Ficticia','Av. Demo 100','Calle Prueba 1','estandar',1,'creado',      now() - interval '120 minutes'),
 ('ENV-DEMO0002','Tienda Ficticia B','Pedro Ficticio','Av. Demo 200','Calle Prueba 2','express', 2,'creado',      now() - interval '110 minutes'),
 ('ENV-DEMO0003','Tienda Ficticia A','Ana Ficticia',  'Av. Demo 300','Calle Prueba 3','estandar',1,'asignado',    now() - interval '100 minutes'),
 ('ENV-DEMO0004','Tienda Ficticia C','Luis Ficticio', 'Av. Demo 400','Calle Prueba 4','express', 3,'retirado',    now() - interval '90 minutes'),
 ('ENV-DEMO0005','Tienda Ficticia B','Rosa Ficticia', 'Av. Demo 500','Calle Prueba 5','estandar',2,'en_transito', now() - interval '80 minutes'),
 ('ENV-DEMO0006','Tienda Ficticia C','Maria Ficticia','Av. Demo 600','Calle Prueba 6','express', 3,'entregado',   now() - interval '200 minutes'),
 ('ENV-DEMO0007','Tienda Ficticia A','Jorge Ficticio','Av. Demo 700','Calle Prueba 7','estandar',1,'incidencia',  now() - interval '75 minutes'),
 ('ENV-DEMO0008','Tienda Ficticia B','Elena Ficticia','Av. Demo 800','Calle Prueba 8','estandar',2,'cancelado',   now() - interval '150 minutes');

-- Historial de cada envio (la fecha se calcula "hace N minutos")
SELECT _ev('ENV-DEMO0001', NULL, 'creado', 'cliente', 120);
SELECT _ev('ENV-DEMO0002', NULL, 'creado', 'cliente', 110);
SELECT _ev('ENV-DEMO0003', NULL, 'creado', 'cliente', 100);
SELECT _ev('ENV-DEMO0003', 'creado', 'asignado', 'operador', 95, 'Asignado a Repartidor Ficticio 1');
SELECT _ev('ENV-DEMO0004', NULL, 'creado', 'cliente', 90);
SELECT _ev('ENV-DEMO0004', 'creado', 'asignado', 'operador', 85, 'Asignado a Repartidor Ficticio 1');
SELECT _ev('ENV-DEMO0004', 'asignado', 'asignado', 'repartidor-1', 80, 'Asignacion aceptada por el repartidor');
SELECT _ev('ENV-DEMO0004', 'asignado', 'retirado', 'repartidor-1', 70);
SELECT _ev('ENV-DEMO0005', NULL, 'creado', 'cliente', 80);
SELECT _ev('ENV-DEMO0005', 'creado', 'asignado', 'operador', 75, 'Asignado a Repartidor Ficticio 2');
SELECT _ev('ENV-DEMO0005', 'asignado', 'asignado', 'repartidor-2', 70, 'Asignacion aceptada por el repartidor');
SELECT _ev('ENV-DEMO0005', 'asignado', 'retirado', 'repartidor-2', 60);
SELECT _ev('ENV-DEMO0005', 'retirado', 'en_transito', 'repartidor-2', 50);
SELECT _ev('ENV-DEMO0006', NULL, 'creado', 'cliente', 200);
SELECT _ev('ENV-DEMO0006', 'creado', 'asignado', 'operador', 190, 'Asignado a Repartidor Ficticio 2');
SELECT _ev('ENV-DEMO0006', 'asignado', 'asignado', 'repartidor-2', 185, 'Asignacion aceptada por el repartidor');
SELECT _ev('ENV-DEMO0006', 'asignado', 'retirado', 'repartidor-2', 170);
SELECT _ev('ENV-DEMO0006', 'retirado', 'en_transito', 'repartidor-2', 150);
SELECT _ev('ENV-DEMO0006', 'en_transito', 'entregado', 'repartidor-2', 120);
SELECT _ev('ENV-DEMO0007', NULL, 'creado', 'cliente', 75);
SELECT _ev('ENV-DEMO0007', 'creado', 'asignado', 'operador', 70, 'Asignado a Repartidor Ficticio 2');
SELECT _ev('ENV-DEMO0007', 'asignado', 'asignado', 'repartidor-2', 65, 'Asignacion aceptada por el repartidor');
SELECT _ev('ENV-DEMO0007', 'asignado', 'retirado', 'repartidor-2', 55);
SELECT _ev('ENV-DEMO0007', 'retirado', 'en_transito', 'repartidor-2', 45);
SELECT _ev('ENV-DEMO0007', 'en_transito', 'incidencia', 'repartidor-2', 30, 'Destinatario ausente; se reintentara la entrega');
SELECT _ev('ENV-DEMO0008', NULL, 'creado', 'cliente', 150);
SELECT _ev('ENV-DEMO0008', 'creado', 'cancelado', 'cliente', 140);
DROP FUNCTION _ev(TEXT, TEXT, TEXT, TEXT, INT, TEXT);

-- Asignaciones coherentes con los estados (activas salvo la del envio ya entregado)
INSERT INTO asignaciones (envio_id, repartidor_id, activa, aceptada_en, creada_en)
SELECT e.id, v.rep, v.activa, CASE WHEN v.acepta THEN now() - interval '60 minutes' END, now() - interval '100 minutes'
FROM (VALUES ('ENV-DEMO0003',1,TRUE,FALSE), ('ENV-DEMO0004',1,TRUE,TRUE), ('ENV-DEMO0005',2,TRUE,TRUE),
             ('ENV-DEMO0006',2,FALSE,TRUE), ('ENV-DEMO0007',2,TRUE,TRUE)) AS v(codigo, rep, activa, acepta)
JOIN envios e ON e.codigo = v.codigo;

-- Un aviso por envio para que el worker construya la busqueda en Mongo al arrancar
INSERT INTO outbox (envio_id) SELECT id FROM envios;

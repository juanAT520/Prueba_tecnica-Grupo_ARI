-- =====================================================================
-- Grupo ARI - Prueba Técnica Analista de Datos
-- Esquema relacional (modelo en estrella) para unificar:
--   - Precios de carburantes (Geoportal Gasolineras, Ministerio)
--   - Matriculaciones de vehículos (DGT)
-- Motor: PostgreSQL
-- =====================================================================

-- Limpieza (permite re-ejecutar el script sin errores)
DROP TABLE IF EXISTS fact_precios_carburante CASCADE;
DROP TABLE IF EXISTS fact_matriculaciones CASCADE;
DROP TABLE IF EXISTS dim_estacion CASCADE;
DROP TABLE IF EXISTS dim_municipio_alias CASCADE;
DROP TABLE IF EXISTS dim_municipio CASCADE;
DROP TABLE IF EXISTS dim_provincia CASCADE;
DROP TABLE IF EXISTS dim_tiempo CASCADE;

-- ---------------------------------------------------------------------
-- DIM_PROVINCIA
-- Solo 2 provincias en el alcance del ejercicio (Las Palmas / Sta. Cruz
-- de Tenerife). cod_provincia = código INE (35 / 38).
-- ---------------------------------------------------------------------
CREATE TABLE dim_provincia (
    cod_provincia       VARCHAR(2)  PRIMARY KEY,   -- '35' / '38' (código INE)
    cod_provincia_dgt   VARCHAR(2)  NOT NULL,       -- 'GC' / 'TF' (código alfabético DGT)
    nombre_provincia    VARCHAR(60) NOT NULL
);

COMMENT ON TABLE dim_provincia IS
  'Dimensión de provincia. Se mantienen ambos códigos (INE numérico y DGT alfabético) '
  'porque cada fuente original usa un sistema distinto.';

-- ---------------------------------------------------------------------
-- DIM_MUNICIPIO
-- Clave canónica = código INE de municipio (de matriculaciones, fuente
-- autoritativa). Incluye el nombre "oficial" (abreviado, tal como lo usa
-- la DGT) y el nombre "largo" cuando se conoce (vía carburantes).
-- ---------------------------------------------------------------------
CREATE TABLE dim_municipio (
    municipio_id        SERIAL       PRIMARY KEY,
    cod_ine_municipio    VARCHAR(5)   UNIQUE,        -- código INE (5 dígitos), NULL si desconocido
    nombre_municipio_dgt VARCHAR(30)  NOT NULL,       -- nombre tal como aparece en matriculaciones DGT
    nombre_municipio_normalizado VARCHAR(60) NOT NULL, -- nombre usado para el cruce entre fuentes
    cod_provincia        VARCHAR(2)   NOT NULL REFERENCES dim_provincia(cod_provincia)
);

COMMENT ON TABLE dim_municipio IS
  'Dimensión de municipio. Es el punto de unión entre ambas fuentes de datos. '
  'Los nombres de municipio no siguen la misma convención en DGT (abreviada, '
  'p.ej. "S C TENERIFE") que en el Geoportal de Gasolineras (p.ej. "Santa Cruz '
  'de Tenerife"), por lo que se aplica una normalización + tabla de alias '
  '(ver dim_municipio_alias) en el proceso ETL (scripts/db_utils.py).';

-- ---------------------------------------------------------------------
-- DIM_MUNICIPIO_ALIAS
-- Tabla de auditoría: documenta qué nombre "crudo" de cada fuente se
-- mapeó a qué municipio_id, para trazabilidad del proceso de unificación.
-- ---------------------------------------------------------------------
CREATE TABLE dim_municipio_alias (
    alias_id       SERIAL      PRIMARY KEY,
    fuente         VARCHAR(20) NOT NULL,   -- 'carburantes' | 'matriculaciones'
    nombre_crudo   VARCHAR(60) NOT NULL,
    municipio_id   INTEGER     NOT NULL REFERENCES dim_municipio(municipio_id)
);

-- ---------------------------------------------------------------------
-- DIM_TIEMPO
-- Dimensión de fecha compartida por ambos hechos.
-- ---------------------------------------------------------------------
CREATE TABLE dim_tiempo (
    fecha        DATE PRIMARY KEY,
    anio         SMALLINT NOT NULL,
    mes          SMALLINT NOT NULL,
    dia          SMALLINT NOT NULL,
    trimestre    SMALLINT NOT NULL,
    nombre_mes   VARCHAR(15) NOT NULL
);

-- ---------------------------------------------------------------------
-- DIM_ESTACION
-- Una fila por estación de servicio (carburantes).
-- ---------------------------------------------------------------------
CREATE TABLE dim_estacion (
    id_estacion    INTEGER      PRIMARY KEY,   -- IDEESS de la API
    rotulo         VARCHAR(100),
    direccion      VARCHAR(200),
    horario        VARCHAR(100),
    latitud        NUMERIC(10,6),
    longitud       NUMERIC(10,6),
    margen         VARCHAR(1),
    tipo_venta     VARCHAR(1),
    codigo_postal  VARCHAR(5),
    municipio_id   INTEGER REFERENCES dim_municipio(municipio_id)
);

-- ---------------------------------------------------------------------
-- FACT_MATRICULACIONES
-- Grano: 1 fila = 1 vehículo matriculado.
-- ---------------------------------------------------------------------
CREATE TABLE fact_matriculaciones (
    matriculacion_id      BIGSERIAL PRIMARY KEY,
    fecha_matriculacion   DATE NOT NULL REFERENCES dim_tiempo(fecha),
    municipio_id           INTEGER REFERENCES dim_municipio(municipio_id),
    cod_provincia           VARCHAR(2) NOT NULL REFERENCES dim_provincia(cod_provincia),
    marca                   VARCHAR(30),
    modelo                  VARCHAR(22),
    cod_tipo_vehiculo        VARCHAR(2),
    cod_propulsion            VARCHAR(1),
    ind_nuevo_usado            VARCHAR(1),
    persona_fisica_juridica     VARCHAR(1),
    servicio                     VARCHAR(3),
    co2                            NUMERIC(6,2),
    codigo_postal                   VARCHAR(5)
);

CREATE INDEX idx_fact_mat_municipio ON fact_matriculaciones(municipio_id);
CREATE INDEX idx_fact_mat_fecha ON fact_matriculaciones(fecha_matriculacion);
CREATE INDEX idx_fact_mat_provincia ON fact_matriculaciones(cod_provincia);

-- ---------------------------------------------------------------------
-- FACT_PRECIOS_CARBURANTE
-- Grano: 1 fila = 1 estación x fecha de extracción (permite histórico si
-- el proceso de extracción se ejecuta periódicamente).
-- ---------------------------------------------------------------------
CREATE TABLE fact_precios_carburante (
    precio_id                BIGSERIAL PRIMARY KEY,
    id_estacion               INTEGER NOT NULL REFERENCES dim_estacion(id_estacion),
    municipio_id                INTEGER REFERENCES dim_municipio(municipio_id),
    cod_provincia                 VARCHAR(2) NOT NULL REFERENCES dim_provincia(cod_provincia),
    fecha_extraccion               DATE NOT NULL REFERENCES dim_tiempo(fecha),
    precio_gasoleo_a                 NUMERIC(5,3),
    precio_gasoleo_premium             NUMERIC(5,3),
    precio_gasolina_95_e5                NUMERIC(5,3),
    precio_gasolina_98_e5                  NUMERIC(5,3),
    precio_glp                               NUMERIC(5,3),
    precio_gnc                                 NUMERIC(5,3)
);

CREATE INDEX idx_fact_precios_municipio ON fact_precios_carburante(municipio_id);
CREATE INDEX idx_fact_precios_fecha ON fact_precios_carburante(fecha_extraccion);
CREATE INDEX idx_fact_precios_estacion ON fact_precios_carburante(id_estacion);

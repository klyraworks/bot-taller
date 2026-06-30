import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def get_conn():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id            SERIAL PRIMARY KEY,
            telegram_id   BIGINT UNIQUE NOT NULL,
            username      TEXT,
            nombre        TEXT NOT NULL,
            rol           TEXT NOT NULL CHECK (rol IN ('admin', 'jefe', 'mecanico')),
            password_hash TEXT,
            is_active     BOOLEAN NOT NULL DEFAULT TRUE,
            created_at    TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at    TIMESTAMP NOT NULL DEFAULT NOW(),
            deleted_at    TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS servicios (
            id                SERIAL PRIMARY KEY,
            tricimoto_num     TEXT NOT NULL,
            tricimoto_color   TEXT NOT NULL,
            monto_total       NUMERIC(10,2) NOT NULL CHECK (monto_total >= 0),
            monto_pendiente   NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (monto_pendiente >= 0),
            descripcion       TEXT DEFAULT 'Sin descripción',
            mecanico_id       INTEGER NOT NULL REFERENCES usuarios(id),
            registrado_por    INTEGER NOT NULL REFERENCES usuarios(id),
            estado            TEXT NOT NULL DEFAULT 'pagado' CHECK (estado IN ('pendiente', 'pagado', 'anulado')),
            is_active         BOOLEAN NOT NULL DEFAULT TRUE,
            created_at        TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at        TIMESTAMP NOT NULL DEFAULT NOW(),
            deleted_at        TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS pagos (
            id             SERIAL PRIMARY KEY,
            servicio_id    INTEGER NOT NULL REFERENCES servicios(id),
            monto          NUMERIC(10,2) NOT NULL CHECK (monto > 0),
            registrado_por INTEGER NOT NULL REFERENCES usuarios(id),
            is_active      BOOLEAN NOT NULL DEFAULT TRUE,
            created_at     TIMESTAMP NOT NULL DEFAULT NOW(),
            deleted_at     TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS gastos (
            id             SERIAL PRIMARY KEY,
            tipo           TEXT NOT NULL CHECK (tipo IN ('gasto', 'adelanto')),
            monto          NUMERIC(10,2) NOT NULL CHECK (monto > 0),
            descripcion    TEXT,
            registrado_por INTEGER NOT NULL REFERENCES usuarios(id),
            is_active      BOOLEAN NOT NULL DEFAULT TRUE,
            created_at     TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at     TIMESTAMP NOT NULL DEFAULT NOW(),
            deleted_at     TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS logs (
            id             SERIAL PRIMARY KEY,
            accion         TEXT NOT NULL,
            tabla          TEXT NOT NULL,
            registro_id    INTEGER,
            detalle        TEXT,
            registrado_por INTEGER REFERENCES usuarios(id),
            created_at     TIMESTAMP NOT NULL DEFAULT NOW()
        );
        
        -- Índices
        CREATE INDEX IF NOT EXISTS idx_servicios_mecanico    ON servicios(mecanico_id);
        CREATE INDEX IF NOT EXISTS idx_servicios_estado      ON servicios(estado);
        CREATE INDEX IF NOT EXISTS idx_servicios_created_at  ON servicios(created_at);
        CREATE INDEX IF NOT EXISTS idx_servicios_tricimoto   ON servicios(tricimoto_num, tricimoto_color);
        CREATE INDEX IF NOT EXISTS idx_pagos_servicio        ON pagos(servicio_id);
        CREATE INDEX IF NOT EXISTS idx_gastos_tipo           ON gastos(tipo);
        CREATE INDEX IF NOT EXISTS idx_gastos_created_at     ON gastos(created_at);
        CREATE INDEX IF NOT EXISTS idx_logs_tabla_registro   ON logs(tabla, registro_id);
        CREATE INDEX IF NOT EXISTS idx_logs_created_at       ON logs(created_at);
        
        -- Trigger updated_at
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        
        CREATE TRIGGER trg_usuarios_updated_at
            BEFORE UPDATE ON usuarios
            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        
        CREATE TRIGGER trg_servicios_updated_at
            BEFORE UPDATE ON servicios
            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        
        CREATE TRIGGER trg_gastos_updated_at
            BEFORE UPDATE ON gastos
            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    """)
    conn.commit()
    cur.close()
    conn.close()

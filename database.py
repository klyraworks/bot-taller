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
            id SERIAL PRIMARY KEY,
            telegram_id BIGINT UNIQUE NOT NULL,
            username TEXT,
            nombre TEXT NOT NULL,
            rol TEXT NOT NULL CHECK (rol IN ('admin', 'jefe', 'mecanico')),
            activo BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS servicios (
            id SERIAL PRIMARY KEY,
            fecha TIMESTAMP DEFAULT NOW(),
            tricimoto_num TEXT NOT NULL,
            tricimoto_color TEXT NOT NULL,
            monto_total NUMERIC(10,2) NOT NULL,
            monto_pendiente NUMERIC(10,2) DEFAULT 0,
            descripcion TEXT,
            mecanico_id INTEGER REFERENCES usuarios(id),
            registrado_por INTEGER REFERENCES usuarios(id),
            estado TEXT DEFAULT 'activo'
        );

        CREATE TABLE IF NOT EXISTS pagos (
            id SERIAL PRIMARY KEY,
            fecha TIMESTAMP DEFAULT NOW(),
            servicio_id INTEGER REFERENCES servicios(id),
            monto NUMERIC(10,2) NOT NULL,
            registrado_por INTEGER REFERENCES usuarios(id)
        );

        CREATE TABLE IF NOT EXISTS gastos (
            id SERIAL PRIMARY KEY,
            fecha TIMESTAMP DEFAULT NOW(),
            tipo TEXT NOT NULL CHECK (tipo IN ('gasto', 'adelanto')),
            monto NUMERIC(10,2) NOT NULL,
            descripcion TEXT,
            registrado_por INTEGER REFERENCES usuarios(id)
        );
    """)

    conn.commit()
    cur.close()
    conn.close()

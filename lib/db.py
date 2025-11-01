import os
import streamlit as st
import psycopg
import psycopg.rows
from psycopg_pool import ConnectionPool

def _dsn() -> str:
    v = os.getenv("DATABASE_URL")
    if v:
        return v
    try:
        return st.secrets["DATABASE_URL"]
    except Exception as e:
        raise RuntimeError("Configure DATABASE_URL em env var ou st.secrets") from e

@st.cache_resource(show_spinner=False)
def get_pool():
    return ConnectionPool(
        conninfo=_dsn(),
        min_size=0,   # sem conexões ociosas
        max_size=4,   # baixo para servidor serverless
        max_idle=60,
        timeout=20,   # tempo pra obter conexão do pool
    )


def q_all(sql: str, params=None):
    with get_pool().connection() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(sql, params or ())
            return cur.fetchall()

def q_one(sql: str, params=None):
    with get_pool().connection() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(sql, params or ())
            return cur.fetchone()

def q_exec(sql: str, params=None) -> int:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            conn.commit()
            return cur.rowcount or 0

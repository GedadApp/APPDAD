# lib/db.py — acesso simples ao Postgres (psycopg 3), sem pool
import os
import psycopg
import psycopg.rows
import streamlit as st

def _dsn() -> str:
    # 1) Streamlit Secrets
    if "DATABASE_URL" in st.secrets:
        return st.secrets["DATABASE_URL"]
    # 2) Variável de ambiente (dev)
    env = os.getenv("DATABASE_URL")
    if env:
        return env
    raise RuntimeError("Defina DATABASE_URL em Settings → Secrets ou como variável de ambiente.")

def q_all(sql: str, params=None):
    with psycopg.connect(_dsn()) as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(sql, params or ())
            return cur.fetchall()

def q_one(sql: str, params=None):
    with psycopg.connect(_dsn()) as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(sql, params or ())
            return cur.fetchone()

def q_exec(sql: str, params=None) -> int:
    with psycopg.connect(_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            conn.commit()
            return cur.rowcount or 0

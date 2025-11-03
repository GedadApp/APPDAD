# lib/db.py — versão simples (sem pool)
import os
import streamlit as st
import psycopg, psycopg.rows

def _dsn() -> str:
    # 1) Secrets (Streamlit Cloud): DATABASE_URL
    if "DATABASE_URL" in st.secrets:
        return st.secrets["DATABASE_URL"]
    # 2) Ambiente local (dev)
    v = os.getenv("DATABASE_URL")
    if v:
        return v
    raise RuntimeError("Defina DATABASE_URL em Secrets ou env var.")

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

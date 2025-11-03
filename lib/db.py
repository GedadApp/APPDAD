# lib/db.py — acesso simples ao Postgres (psycopg 3), sem pool
import os
import psycopg
import psycopg.rows
import streamlit as st
from urllib.parse import quote, urlparse, parse_qsl, urlencode, urlunparse

def _add_param_if_missing(uri: str, key: str, value: str) -> str:
    u = urlparse(uri)
    q = dict(parse_qsl(u.query, keep_blank_values=True))
    if key not in q:
        q[key] = value
    return urlunparse((u.scheme, u.netloc, u.path, u.params, urlencode(q), u.fragment))

def _dsn() -> str:
    # 1) DSN direto em Secrets
    if "DATABASE_URL" in st.secrets:
        dsn = st.secrets["DATABASE_URL"]
        dsn = _add_param_if_missing(dsn, "sslmode", "require")
        dsn = _add_param_if_missing(dsn, "connect_timeout", "8")
        return dsn

    # 2) Bloco [pg] em Secrets
    if "pg" in st.secrets:
        pg = st.secrets["pg"]
        user   = str(pg.get("user", "")).strip()
        pwd    = str(pg.get("password", "")).strip()
        host   = str(pg.get("host", "")).strip()
        port   = str(pg.get("port", "5432")).strip()
        dbname = str(pg.get("dbname", "postgres")).strip()

        if not (user and pwd and host and port and dbname):
            raise RuntimeError("Secrets [pg] incompletos: defina user, password, host, port, dbname.")

        # password com caracteres especiais precisa de percent-encode
        pwd_enc = quote(pwd, safe="")
        return f"postgresql://{user}:{pwd_enc}@{host}:{port}/{dbname}?sslmode=require&connect_timeout=8"

    # 3) Variável de ambiente (dev/local)
    env = os.getenv("DATABASE_URL")
    if env:
        env = _add_param_if_missing(env, "sslmode", "require")
        env = _add_param_if_missing(env, "connect_timeout", "8")
        return env

    # Nenhuma fonte encontrada
    raise RuntimeError("Defina DATABASE_URL nos Secrets OU um bloco [pg] com user/password/host/port/dbname.")

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

# Aliases para compatibilidade, caso seu código antigo use estes nomes:
def qall(sql: str, params=None):  # opcional
    return q_all(sql, params)

def qone(sql: str, params=None):  # opcional
    return q_one(sql, params)

def qexec(sql: str, params=None) -> int:  # opcional
    return q_exec(sql, params)

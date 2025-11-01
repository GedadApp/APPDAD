import os
import socket
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

import streamlit as st
import psycopg
import psycopg.rows
from psycopg_pool import ConnectionPool

# -------- URL helpers --------
def _dsn() -> str:
    v = os.getenv("DATABASE_URL")
    if v:
        return v
    try:
        return st.secrets["DATABASE_URL"]
    except Exception as e:
        raise RuntimeError("Configure DATABASE_URL em env var ou st.secrets") from e

def _add_query_param(uri: str, key: str, value: str) -> str:
    u = urlparse(uri)
    q = dict(parse_qsl(u.query, keep_blank_values=True))
    # não sobrescreve se já existir
    q.setdefault(key, value)
    return urlunparse((u.scheme, u.netloc, u.path, u.params, urlencode(q), u.fragment))

def _force_ipv4_hostaddr(uri: str) -> str:
    # resolve host → IPv4 e injeta hostaddr na URI (mantém host p/ TLS)
    u = urlparse(uri)
    host = u.hostname
    port = u.port or 5432
    if not host:
        return uri
    try:
        for fam, _, _, _, sa in socket.getaddrinfo(host, port, family=socket.AF_INET):
            ipv4 = sa[0]
            if ipv4:
                return _add_query_param(uri, "hostaddr", ipv4)
    except Exception:
        pass
    return uri

def _normalized_conninfo() -> str:
    dsn = _dsn()
    dsn = _add_query_param(dsn, "sslmode", "require")
    dsn = _add_query_param(dsn, "connect_timeout", "8")
    # força IPv4; funciona tanto no host 5432 quanto no pooler 6543
    dsn = _force_ipv4_hostaddr(dsn)
    return dsn

# -------- Pool (opcional) + Fallback direto --------
USE_PG_POOL = os.getenv("USE_PG_POOL", "true").lower() in ("1", "true", "yes", "on")

@st.cache_resource(show_spinner=False)
def _pool() -> ConnectionPool:
    return ConnectionPool(
        conninfo=_normalized_conninfo(),
        min_size=0,
        max_size=4,
        max_idle=60,
        timeout=20,
    )

def _connect_direct():
    # conexão direta (sem pool), útil para ambientes problemáticos
    return psycopg.connect(_normalized_conninfo())

def q_all(sql: str, params=None):
    if USE_PG_POOL:
        with _pool().connection() as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                cur.execute(sql, params or ())
                return cur.fetchall()
    else:
        # modo direto
        with _connect_direct() as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                cur.execute(sql, params or ())
                return cur.fetchall()

def q_one(sql: str, params=None):
    if USE_PG_POOL:
        with _pool().connection() as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                cur.execute(sql, params or ())
                return cur.fetchone()
    else:
        with _connect_direct() as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                cur.execute(sql, params or ())
                return cur.fetchone()

def q_exec(sql: str, params=None) -> int:
    if USE_PG_POOL:
        with _pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params or ())
                conn.commit()
                return cur.rowcount or 0
    else:
        with _connect_direct() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params or ())
                conn.commit()
                return cur.rowcount or 0

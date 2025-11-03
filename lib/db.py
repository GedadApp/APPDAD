# lib/db.py — simples, sem pool, forçando IPv4 automaticamente
import os
import socket
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

import streamlit as st
import psycopg
import psycopg.rows

# ---------- helpers de URL ----------
def _raw_dsn() -> str:
    if "DATABASE_URL" in st.secrets:
        return st.secrets["DATABASE_URL"]
    v = os.getenv("DATABASE_URL")
    if v:
        return v
    raise RuntimeError("Defina DATABASE_URL em Secrets ou env var.")

def _add_qparam(uri: str, key: str, value: str) -> str:
    u = urlparse(uri)
    q = dict(parse_qsl(u.query, keep_blank_values=True))
    # não sobrescreve se já existir
    q.setdefault(key, value)
    return urlunparse((u.scheme, u.netloc, u.path, u.params, urlencode(q), u.fragment))

def _force_ipv4_hostaddr(uri: str) -> str:
    """
    Resolve o host para IPv4 e injeta hostaddr=<ipv4> na URI.
    Mantém o 'host' original para o TLS validar o certificado.
    """
    u = urlparse(uri)
    host = u.hostname
    port = u.port or 5432
    if not host:
        return uri
    try:
        infos = socket.getaddrinfo(host, port, family=socket.AF_INET)  # apenas IPv4
        if infos:
            ipv4 = infos[0][4][0]
            return _add_qparam(uri, "hostaddr", ipv4)
    except Exception:
        # se não conseguir resolver IPv4, retorna a original (deixa o libpq tentar)
        pass
    return uri

def _dsn() -> str:
    dsn = _raw_dsn()
    dsn = _add_qparam(dsn, "sslmode", "require")
    dsn = _add_qparam(dsn, "connect_timeout", "8")
    dsn = _force_ipv4_hostaddr(dsn)
    return dsn

# ---------- funções de acesso (sem pool) ----------
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

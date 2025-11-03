# lib/db.py — simples (sem pool)
import os
import streamlit as st
import psycopg, psycopg.rows

def _dsn() -> str:
    if "DATABASE_URL" in st.secrets:
        return st.secrets["DATABASE_URL"]
    v = os.getenv("DATABASE_URL")
    if v:
        return v
    raise RuntimeError("Defina DATABASE_URL em Secrets ou env var.")

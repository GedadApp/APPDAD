import streamlit as st

st.set_page_config(page_title="GEDAD – Home", page_icon="🏠", layout="wide", initial_sidebar_state="expanded")

st.title("GEDAD – Sistemas Integrados (Projeto de Teste Multipáginas)")
st.markdown(
    """
    Use o menu lateral para acessar as páginas. Nesta etapa, só a **Agenda** está ativa.

    **Dica de performance**: no modo multipáginas, apenas a página aberta é executada a cada rerun.
    """
)
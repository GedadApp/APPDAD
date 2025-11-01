import streamlit as st
import pandas as pd
from datetime import date, time
from lib.db import q_all, q_one, q_exec

st.set_page_config(page_title="Agenda", page_icon="📅", layout="wide")

# ===================== AJUSTES DE BANCO / ÍNDICES =====================
def ensure_agenda_indexes():
    q_exec("""
        create index if not exists agenda_entidade_data_idx on agenda (entidade, data);
    """)
    q_exec("""
        create unique index if not exists agenda_unq_ent_data_ind on agenda (entidade, data, indice);
    """)
    q_exec("""
        create index if not exists agenda_status_idx on agenda (status);
    """)

ensure_agenda_indexes()

# ===================== HELPERS =====================
@st.cache_data(ttl=300, show_spinner=False)
def load_entidades() -> list[str]:
    rows = q_all("select distinct entidade from agenda where entidade is not null order by 1")
    return [r["entidade"] for r in rows]

@st.cache_data(ttl=300, show_spinner=False)
def get_consulentes_sugestoes(prefixo: str) -> list[dict]:
    """Busca em 'leitores' (se existir) para sugestão rápida.
    Retorna lista: {id, nome, telefone}.
    """
    try:
        ok = q_one("select to_regclass('public.leitores') is not null as ok")["ok"]
        if not ok:
            return []
        prefixo = prefixo.strip()
        if len(prefixo) < 3:
            return []
        return q_all(
            """
            select id, nome, telefone
              from leitores
             where nome ilike %s
             order by nome asc
             limit 50
            """,
            (f"%{prefixo}%",),
        )
    except Exception:
        return []

def next_free_index(entidade: str, dt: date) -> int:
    row = q_one(
        """
        with slots as (select generate_series(1,12) i)
        select coalesce(min(s.i), 12) as prox
          from slots s
          left join agenda a
            on a.indice = s.i and a.entidade=%s and a.data=%s
         where a.indice is null
        """,
        (entidade, dt),
    )
    return int(row["prox"] or 12)

def list_agenda(entidade: str, dt: date, last_id: int | None, limit: int = 100):
    rows = q_all(
        """
        select id, indice, consulente, status, hora_chegada, criado_em
          from agenda
         where entidade=%s and data=%s
           and (%s is null or id > %s)
         order by id
         limit %s
        """,
        (entidade, dt, last_id, last_id, limit),
    )
    next_cursor = rows[-1]["id"] if rows else None
    return rows, next_cursor

# ===================== UI =====================
st.title("📅 Agenda – 1 data, índices 1..12")

left, right = st.columns([2, 1])
with left:
    entidades = load_entidades()
    entidade = st.selectbox(
        "Entidade",
        options=(entidades + ["(digitar…)"]) if entidades else ["(digitar…)"]
    )
    if entidade == "(digitar…)":
        entidade = st.text_input("Informe a entidade", placeholder="EX: CABOCLO, PRETO VELHO…").strip()

with right:
    data_escolhida = st.date_input("Data", value=date.today(), format="DD/MM/YYYY")

if not entidade:
    st.info("Informe uma **Entidade** para continuar.")
    st.stop()

st.divider()

# ---- Busca rápida de consulente (opcional) ----
with st.expander("🔎 Buscar consulente em 'leitores' (opcional)"):
    prefixo = st.text_input("Nome contém…", placeholder="digite ao menos 3 letras")
    encontrados = get_consulentes_sugestoes(prefixo)
    escolha = None
    if encontrados:
        escolha = st.selectbox(
            "Resultados",
            options=[None] + encontrados,
            format_func=lambda r: "—" if r is None else f"{r['nome']}  ·  {r.get('telefone') or 's/ telefone'}",
        )
        if escolha:
            st.success("Consulente selecionado. Os campos serão preenchidos na criação.")

# ===================== FORM NOVO AGENDAMENTO =====================
with st.form("novo_agendamento", clear_on_submit=True):
    st.subheader("➕ Novo agendamento")
    cols = st.columns([2, 2, 1])

    nome_default = (escolha or {}).get("nome") if escolha else ""
    consulente = cols[0].text_input("Consulente", value=nome_default)

    status = cols[1].selectbox(
        "Status",
        options=["AGUARDANDO", "AGENDADO", "EM ATENDIMENTO", "FINALIZADO"],
        index=0,
    )

    prox = next_free_index(entidade, data_escolhida)
    cols[2].text_input("Índice (auto)", value=str(prox), disabled=True)

    # Hora de chegada: toggle seguro (evita problemas de None no time_input)
    usar_hora = st.checkbox("Definir hora de chegada", value=False)
    hora = None
    if usar_hora:
        hora = st.time_input("Hora de chegada", value=time(0, 0), step=300, key="hora_chegada_input")

    salvar = st.form_submit_button("Salvar", type="primary")

if salvar:
    try:
        q_exec(
            """
            insert into agenda (entidade, data, indice, consulente, status, hora_chegada, criado_em)
            values (%s, %s, %s, %s, %s, %s, now())
            """,
            (entidade, data_escolhida, prox, consulente or None, status, hora),
        )
        st.toast("✅ Agendamento salvo.")
        st.rerun()
    except Exception as e:
        st.error(f"❌ Erro ao salvar: {e}")

st.divider()

# ===================== LISTAGEM COM PAGINAÇÃO =====================
st.session_state.setdefault("cursor_agenda", None)

rows, next_cursor = list_agenda(entidade, data_escolhida, st.session_state.get("cursor_agenda"))

if not rows:
    st.info("Nenhum agendamento encontrado para os filtros.")
else:
    df = pd.DataFrame(rows).copy()

    # Converte hora_chegada para dtype time onde possível
    def _parse_time(x):
        if x is None or x == "":
            return None
        if isinstance(x, time):
            return x
        try:
            s = str(x)
            hh, mm, *rest = s.split(":")
            return time(int(hh), int(mm))
        except Exception:
            return None

    df["hora_chegada"] = df["hora_chegada"].apply(_parse_time)

    # Editor com apenas status e hora_chegada editáveis
    df = df.set_index("id", drop=True)

    edited = st.data_editor(
        df,
        use_container_width=True,
        num_rows="fixed",
        hide_index=False,
        column_config={
            "indice": st.column_config.NumberColumn("Índice", help="1..12", disabled=True),
            "consulente": st.column_config.TextColumn("Consulente", disabled=True),
            "status": st.column_config.SelectboxColumn(
                "Status",
                options=["AGUARDANDO", "AGENDADO", "EM ATENDIMENTO", "FINALIZADO"],
            ),
            "hora_chegada": st.column_config.TimeColumn("Hora chegada", step=300),
            "criado_em": st.column_config.TextColumn("Criado em", disabled=True),
        },
        key="ed_agenda",
    )

    if st.button("💾 Salvar alterações"):
        orig = df
        upd = edited
        alterados = 0
        for rid in upd.index:
            o = orig.loc[rid]
            n = upd.loc[rid]
            if (o["status"] != n["status"]) or (str(o["hora_chegada"]) != str(n["hora_chegada"])):
                q_exec(
                    "update agenda set status=%s, hora_chegada=%s where id=%s",
                    (n["status"], n["hora_chegada"], int(rid)),
                )
                alterados += 1
        st.toast(f"✅ {alterados} registro(s) atualizado(s)")
        st.rerun()

    # Paginação
    cols = st.columns([1,1,6])
    with cols[0]:
        if st.button("🔄 Recarregar"):
            st.session_state["cursor_agenda"] = None
            st.rerun()
    with cols[1]:
        if next_cursor:
            if st.button("➡️ Carregar mais"):
                st.session_state["cursor_agenda"] = next_cursor
                st.rerun()

with st.expander("🔧 Teste de conexão"):
    if st.button("Testar agora"):
        try:
            row = q_one("select current_user, current_database(), inet_server_addr()::text as host, now() as ts")
            st.success("Conectado!")
            st.json(row)
        except Exception as e:
            st.error(f"Falhou: {e}")

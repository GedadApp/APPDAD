# ===================== PÁGINA: 1_Agenda.py (versão defensiva) =====================
import streamlit as st
import pandas as pd
from datetime import date, tim
from lib.db import q_all, q_one, q_exec  # usa seu lib/db.py

st.set_page_config(page_title="Agenda", page_icon="📅", layout="wide")
st.title("📅 Agenda – 1 data, índices 1..12")

# Estado da UI
st.session_state.setdefault("entidades", [])
st.session_state.setdefault("rows_agenda", [])
st.session_state.setdefault("cursor_agenda", None)

# ===================== DIAGNÓSTICO & MANUTENÇÃO (executa só quando clicar) =====================
with st.expander("🔧 Diagnóstico & manutenção", expanded=False):
    c1, c2, c3 = st.columns(3)

    with c1:
        if st.button("Testar conexão agora"):
            try:
                row = q_one("select current_user, current_database(), inet_server_addr()::text as host, now() as ts")
                st.success("Conectado ao banco.")
                st.json(row)
            except Exception as e:
                st.error(f"Falha de conexão: {e}")

    with c2:
        if st.button("Criar/ajustar índices (1x)"):
            try:
                q_exec("create unique index if not exists agenda_unq_ent_data_ind on public.agenda (entidade, data, indice);")
                q_exec("create index if not exists agenda_entidade_data_idx on public.agenda (entidade, data);")
                q_exec("create index if not exists agenda_status_idx         on public.agenda (status);")
                st.success("Índices criados/verificados.")
            except Exception as e:
                st.error(f"Erro ao criar índices: {e}")

    with c3:
        if st.button("Garantir tabela agenda (1x)"):
            try:
                q_exec("""
                    create table if not exists public.agenda (
                      id           bigserial primary key,
                      entidade     text not null,
                      data         date not null,
                      indice       int  not null check (indice between 1 and 12),
                      consulente   text,
                      status       text not null check (status in ('AGUARDANDO','AGENDADO','EM ATENDIMENTO','FINALIZADO')),
                      hora_chegada time,
                      criado_em    timestamp default now()
                    );
                """)
                st.success("Tabela 'agenda' garantida.")
            except Exception as e:
                st.error(f"Erro ao criar tabela: {e}")

# ===================== HELPERS (só são usados quando você clica) =====================
def try_load_entidades() -> list[str]:
    try:
        rows = q_all("select distinct entidade from public.agenda where entidade is not null order by 1")
        return [r["entidade"] for r in rows]
    except Exception as e:
        st.warning(f"Não foi possível carregar entidades agora: {e}")
        return []

def safe_next_index(entidade: str, dt: date) -> int:
    """Menor índice livre (1..12) – se falhar, volta 1 para não travar a UI."""
    try:
        row = q_one(
            """
            with slots as (select generate_series(1,12) i)
            select coalesce(min(s.i), 12) as prox
              from slots s
              left join public.agenda a
                on a.indice = s.i and a.entidade=%s and a.data=%s
             where a.indice is null
            """,
            (entidade, dt),
        )
        return int(row["prox"] or 12)
    except Exception:
        return 1

def fmt_status_bolinha(s: str) -> str:
    s = (s or "").strip().upper()
    if s == "AGUARDANDO":     return "🟢 AGUARDANDO"
    if s == "AGENDADO":       return "🔵 AGENDADO"
    if s == "EM ATENDIMENTO": return "🟡 EM ATENDIMENTO"
    if s == "FINALIZADO":     return "⚪ FINALIZADO"
    return s or "—"

# ===================== FILTROS (sem tocar no banco ainda) =====================
left, right = st.columns([2, 1])

with left:
    st.caption("Carregue as entidades quando quiser (opcional).")
    if st.button("🔄 Carregar entidades do banco"):
        st.session_state["entidades"] = try_load_entidades()

    ents = st.session_state["entidades"]
    if ents:
        escolha = st.selectbox("Entidade", options=(ents + ["(digitar…)"]))
        if escolha == "(digitar…)":
            entidade = st.text_input("Informe a entidade", placeholder="EX: CABOCLO, PRETO VELHO…").strip()
        else:
            entidade = escolha
    else:
        entidade = st.text_input("Entidade", placeholder="EX: CABOCLO, PRETO VELHO…").strip()

with right:
    data_escolhida = st.date_input("Data", value=date.today(), format="DD/MM/YYYY")

if not entidade:
    st.info("Informe uma **Entidade** para continuar.")
    st.stop()

st.divider()

# ===================== NOVO AGENDAMENTO (consulta só na hora de salvar/pegar índice) =====================
with st.form("novo_agendamento", clear_on_submit=True):
    st.subheader("➕ Novo agendamento")
    c1, c2, c3 = st.columns([2, 2, 1])

    consulente = c1.text_input("Consulente")
    status = c2.selectbox("Status", ["AGUARDANDO", "AGENDADO", "EM ATENDIMENTO", "FINALIZADO"], index=0)

    prox = safe_next_index(entidade, data_escolhida)
    c3.text_input("Índice (auto)", value=str(prox), disabled=True)

    usar_hora = st.checkbox("Definir hora de chegada", value=False)
    hora = st.time_input("Hora de chegada", value=time(0, 0), step=300) if usar_hora else None

    salvar = st.form_submit_button("Salvar", type="primary")

if salvar:
    try:
        q_exec(
            """
            insert into public.agenda (entidade, data, indice, consulente, status, hora_chegada, criado_em)
            values (%s, %s, %s, %s, %s, %s, now())
            """,
            (entidade, data_escolhida, prox, consulente or None, status, hora),
        )
        st.success("✅ Agendamento salvo.")
    except Exception as e:
        st.error(f"❌ Erro ao salvar: {e}")

st.divider()

# ===================== LISTAGEM (só consulta quando você mandar) =====================
cA, cB = st.columns([1, 6])
with cA:
    if st.button("🔍 Carregar agenda do dia"):
        try:
            rows = q_all(
                """
                select id, indice, consulente, status, hora_chegada, criado_em
                  from public.agenda
                 where entidade=%s and data=%s
                 order by indice, id
                 limit 200
                """,
                (entidade, data_escolhida),
            )
            st.session_state["rows_agenda"] = rows
        except Exception as e:
            st.warning(f"Não foi possível carregar a agenda agora: {e}")
            st.session_state["rows_agenda"] = []

rows = st.session_state["rows_agenda"]

if not rows:
    st.info("Nenhum agendamento carregado. Clique em **Carregar agenda do dia**.")
else:
    df = pd.DataFrame(rows).copy()
    df.insert(1, "status_bolinha", df["status"].map(fmt_status_bolinha))

    # normaliza hora_chegada
    def _parse_time(x):
        if x in (None, ""): return None
        if isinstance(x, time): return x
        try:
            hh, mm, *_ = str(x).split(":")
            return time(int(hh), int(mm))
        except Exception:
            return None
    df["hora_chegada"] = df["hora_chegada"].apply(_parse_time)

    df = df.set_index("id", drop=True)
    edited = st.data_editor(
        df,
        use_container_width=True,
        num_rows="fixed",
        hide_index=False,
        column_config={
            "indice": st.column_config.NumberColumn("Índice", disabled=True, help="1..12"),
            "status_bolinha": st.column_config.TextColumn(" ", disabled=True, help="Visual"),
            "consulente": st.column_config.TextColumn("Consulente"),
            "status": st.column_config.SelectboxColumn(
                "Status", options=["AGUARDANDO", "AGENDADO", "EM ATENDIMENTO", "FINALIZADO"]
            ),
            "hora_chegada": st.column_config.TimeColumn("Hora chegada", step=300),
            "criado_em": st.column_config.TextColumn("Criado em", disabled=True),
        },
        key="ed_agenda",
    )

    if st.button("💾 Salvar alterações"):
        orig, upd = df, edited
        alterados = 0
        for rid in upd.index:
            o, n = orig.loc[rid], upd.loc[rid]
            if (o["status"] != n["status"]) or (str(o["hora_chegada"]) != str(n["hora_chegada"])):
                try:
                    q_exec("update public.agenda set status=%s, hora_chegada=%s where id=%s",
                           (n["status"], n["hora_chegada"], int(rid)))
                    alterados += 1
                except Exception as e:
                    st.error(f"Falha ao atualizar id {rid}: {e}")
        st.success(f"✅ {alterados} registro(s) atualizado(s)")

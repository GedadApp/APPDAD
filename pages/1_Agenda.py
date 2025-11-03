# ===================== PÁGINA: 1_Agenda.py (normalizada + agrupamento) =====================
import streamlit as st
import pandas as pd
from datetime import date
from lib.db import q_all, q_one, q_exec

st.set_page_config(page_title="Agenda", page_icon="📅", layout="wide")
st.title("📅 Agenda – 1 data (minutos), agrupada por Entidade")

# Estado da UI
st.session_state.setdefault("rows_agenda_groups", {})   # {entidade_id: {"nome":..., "orig":df, "edit":df}}
st.session_state.setdefault("entidades_cache", [])      # [{"id":..,"nome":..}, ...]


# ===================== DIAGNÓSTICO & MANUTENÇÃO =====================
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
                # índices na modelagem nova
                q_exec("create unique index if not exists agenda_unq_ent_data_ind on public.agenda (entidade_id, data, indice);")
                q_exec("create index if not exists agenda_entidade_data_idx on public.agenda (entidade_id, data);")
                q_exec("create index if not exists agenda_status_idx         on public.agenda (status);")
                q_exec("create index if not exists agenda_pessoa_idx         on public.agenda (pessoa_id);")
                st.success("Índices criados/verificados.")
            except Exception as e:
                st.error(f"Erro ao criar índices: {e}")

    with c3:
        if st.button("Garantir esquema normalizado (1x)"):
            try:
                q_exec("""
                    create table if not exists public.entidade (
                      id    bigserial primary key,
                      nome  text not null unique,
                      ativo boolean default true,
                      criado_em timestamp default now()
                    );
                """)
                q_exec("""
                    create table if not exists public.pessoa (
                      id           bigserial primary key,
                      nome         text not null,
                      cpf          text unique,
                      rg           text,
                      dt_nasc      date,
                      criado_em    timestamp default now(),
                      atualizado_em timestamp default now()
                    );
                """)
                q_exec("""
                    create table if not exists public.pessoa_telefone (
                      id         bigserial primary key,
                      pessoa_id  bigint not null references public.pessoa(id) on delete cascade,
                      tipo       text check (tipo in ('CELULAR','FIXO','WHATSAPP','OUTRO')) default 'CELULAR',
                      numero     text not null,
                      principal  boolean default false
                    );
                """)
                q_exec("""
                    create table if not exists public.agenda (
                      id           bigserial primary key,
                      entidade_id  bigint not null references public.entidade(id) on delete restrict,
                      data         date   not null,
                      indice       int    not null check (indice between 1 and 12),
                      pessoa_id    bigint references public.pessoa(id) on delete set null,
                      status       text   not null check (status in ('AGUARDANDO','AGENDADO','EM ATENDIMENTO','FINALIZADO')) default 'AGUARDANDO',
                      hora_chegada smallint,  -- minutos (0..1439)
                      observacao   text,
                      criado_em    timestamp default now()
                    );
                """)
                # constraint/checagem de faixa
                q_exec("alter table public.agenda drop constraint if exists agenda_hora_chegada_chk;")
                q_exec("alter table public.agenda add constraint agenda_hora_chegada_chk check (hora_chegada is null or (hora_chegada between 0 and 1439));")
                st.success("Esquema garantido.")
            except Exception as e:
                st.error(f"Erro ao garantir esquema: {e}")


# ===================== HELPERS =====================
@st.cache_data(ttl=300, show_spinner=False)
def load_entidades() -> list[dict]:
    try:
        return q_all("select id, nome from public.entidade where ativo is true order by nome")
    except Exception as e:
        st.warning(f"Falha ao carregar entidades: {e}")
        return []

def next_free_index(entidade_id: int, dt: date) -> int:
    row = q_one("""
        with slots as (select generate_series(1,12) i)
        select coalesce(min(s.i), 12) as prox
          from slots s
          left join public.agenda a
                 on a.indice = s.i and a.entidade_id=%s and a.data=%s
         where a.indice is null
    """, (entidade_id, dt))
    return int(row["prox"] or 12)

def fmt_status_bolinha(s: str) -> str:
    s = (s or "").strip().upper()
    if s == "AGUARDANDO":     return "🟢 AGUARDANDO"
    if s == "AGENDADO":       return "🔵 AGENDADO"
    if s == "EM ATENDIMENTO": return "🟡 EM ATENDIMENTO"
    if s == "FINALIZADO":     return "⚪ FINALIZADO"
    return s or "—"

def fmt_hhmm(m):
    if m is None: return ""
    try:
        m = int(m)
        return f"{m//60:02d}:{m%60:02d}"
    except Exception:
        return ""

def get_or_create_pessoa(nome: str, telefone: str | None) -> int | None:
    nome = (nome or "").strip()
    if not nome:
        return None
    # tenta achar por nome exato (pode evoluir para trigram depois)
    row = q_one("select id from public.pessoa where nome = %s", (nome,))
    if row:
        pid = int(row["id"])
    else:
        pid = q_one("insert into public.pessoa (nome) values (%s) returning id", (nome,))["id"]

    if telefone:
        # se já tiver principal, não mexe; senão cria um
        has_tel = q_one("select 1 from public.pessoa_telefone where pessoa_id=%s and principal is true limit 1", (pid,))
        if not has_tel:
            q_exec(
                "insert into public.pessoa_telefone (pessoa_id, tipo, numero, principal) values (%s, 'CELULAR', %s, true)",
                (pid, telefone)
            )
    return pid

def list_agenda_by_day(dt: date, entidade_id: int | None = None) -> list[dict]:
    # pega 1 telefone por pessoa (principal->id mais baixo)
    sql = """
        select a.id, a.entidade_id, e.nome as entidade_nome,
               a.data, a.indice,
               a.pessoa_id, p.nome as pessoa_nome,
               coalesce(pt.numero, '') as telefone,
               a.status, a.hora_chegada, a.observacao, a.criado_em
          from public.agenda a
          join public.entidade e on e.id = a.entidade_id
          left join public.pessoa p on p.id = a.pessoa_id
          left join lateral (
                select numero
                  from public.pessoa_telefone t
                 where t.pessoa_id = p.id
                 order by t.principal desc, t.id asc
                 limit 1
          ) pt on true
         where a.data = %s
    """
    params = [dt]
    if entidade_id:
        sql += " and a.entidade_id = %s"
        params.append(entidade_id)
    sql += " order by e.nome asc, a.indice asc, a.id asc"
    return q_all(sql, tuple(params))


# ===================== FILTROS (opcional filtrar por entidade) =====================
left, right = st.columns([2, 1])

with left:
    if st.button("🔄 Recarregar lista de Entidades"):
        st.session_state["entidades_cache"] = load_entidades()
    if not st.session_state["entidades_cache"]:
        st.session_state["entidades_cache"] = load_entidades()

    ents = st.session_state["entidades_cache"]
    ent_opt = [{"id": None, "nome": "(todas)"}] + ents
    escolha = st.selectbox("Filtrar por Entidade (opcional)", options=ent_opt, format_func=lambda r: r["nome"])

with right:
    data_escolhida = st.date_input("Data", value=date.today(), format="DD/MM/YYYY")


st.divider()

# ===================== NOVO AGENDAMENTO =====================
with st.form("novo_agendamento", clear_on_submit=True):
    st.subheader("➕ Novo agendamento")

    c1, c2 = st.columns([2, 2])
    # ENTIDADE (obrigatória)
    entidade_sel = c1.selectbox("Entidade", options=ents, format_func=lambda r: r["nome"])
    entidade_id = entidade_sel["id"]

    # CONSULENTE + TELEFONE
    consulente = c2.text_input("Consulente (Pessoa)").strip()
    tel = st.text_input("Telefone (opcional)")

    c3, c4 = st.columns([2, 1])
    status = c3.selectbox("Status", ["AGUARDANDO", "AGENDADO", "EM ATENDIMENTO", "FINALIZADO"], index=0)

    prox = next_free_index(entidade_id, data_escolhida)
    c4.text_input("Índice (auto – oculto na listagem)", value=str(prox), disabled=True)

    # hora_chegada (minutos) + observação
    c5, c6 = st.columns([1, 3])
    usar_hora = c5.checkbox("Definir hora de chegada", value=False)
    hora_min = c5.number_input("Minutos (0..1439)", min_value=0, max_value=1439, step=5, value=0, disabled=not usar_hora)
    observacao = c6.text_area("Observação", placeholder="Anotações do atendimento (opcional)")

    salvar = st.form_submit_button("Salvar", type="primary")

if salvar:
    try:
        pessoa_id = get_or_create_pessoa(consulente, tel) if consulente else None
        q_exec(
            """
            insert into public.agenda (entidade_id, data, indice, pessoa_id, status, hora_chegada, observacao, criado_em)
            values (%s, %s, %s, %s, %s, %s, %s, now())
            """,
            (entidade_id, data_escolhida, prox, pessoa_id, status, (hora_min if usar_hora else None), (observacao or None)),
        )
        st.success("✅ Agendamento salvo.")
    except Exception as e:
        st.error(f"❌ Erro ao salvar: {e}")

st.divider()

# ===================== LISTAGEM (agrupada por Entidade) =====================
if st.button("🔍 Carregar agenda do dia"):
    try:
        ent_id = escolha["id"]  # None = todas
        rows = list_agenda_by_day(data_escolhida, ent_id)
        # organizar por entidade_id -> DataFrame
        groups = {}
        for r in rows:
            eid = r["entidade_id"]
            g = groups.setdefault(eid, {"nome": r["entidade_nome"], "rows": []})
            g["rows"].append(r)
        # montar dataframes por grupo
        st.session_state["rows_agenda_groups"] = {}
        for eid, g in groups.items():
            df = pd.DataFrame(g["rows"])
            # colunas auxiliares para UI
            df.insert(1, "status_bolinha", df["status"].map(fmt_status_bolinha))
            df.insert(3, "hora_fmt", df["hora_chegada"].apply(fmt_hhmm))
            # não mostrar 'indice' (só usar para ordenar)
            df = df.sort_values(["indice", "id"]).set_index("id", drop=True)
            st.session_state["rows_agenda_groups"][eid] = {"nome": g["nome"], "orig": df.copy(), "edit": df.copy()}
        if not groups:
            st.info("Nenhum agendamento encontrado para os filtros.")
    except Exception as e:
        st.warning(f"Não foi possível carregar a agenda agora: {e}")
        st.session_state["rows_agenda_groups"] = {}

# Render por grupo
if not st.session_state["rows_agenda_groups"]:
    st.info("Clique em **Carregar agenda do dia** para listar os agendamentos.")
else:
    for eid, pack in st.session_state["rows_agenda_groups"].items():
        st.subheader(f"🏷️ Entidade: {pack['nome']}")
        edited = st.data_editor(
            pack["edit"],
            use_container_width=True,
            num_rows="fixed",
            hide_index=False,
            column_config={
                # "indice": removido da UI
                "status_bolinha": st.column_config.TextColumn(" ", disabled=True, help="Visual"),
                "entidade_id": st.column_config.NumberColumn("Entidade ID", disabled=True),
                "entidade_nome": st.column_config.TextColumn("Entidade", disabled=True),
                "pessoa_id": st.column_config.NumberColumn("Pessoa ID", disabled=True),
                "pessoa_nome": st.column_config.TextColumn("Consulente", disabled=True),
                "telefone": st.column_config.TextColumn("Telefone", disabled=True),
                "status": st.column_config.SelectboxColumn(
                    "Status", options=["AGUARDANDO", "AGENDADO", "EM ATENDIMENTO", "FINALIZADO"]
                ),
                "hora_chegada": st.column_config.NumberColumn("Hora chegada (min)", min_value=0, max_value=1439, step=5),
                "hora_fmt": st.column_config.TextColumn("HH:MM", disabled=True),
                "observacao": st.column_config.TextColumn("Observação", disabled=True),
                "criado_em": st.column_config.TextColumn("Criado em", disabled=True),
                "data": st.column_config.TextColumn("Data", disabled=True),
            },
            key=f"ed_agenda_{eid}",
        )

        # Botão de salvar por grupo
        if st.button(f"💾 Salvar alterações – {pack['nome']}", key=f"save_{eid}"):
            orig = pack["orig"]
            upd = edited
            alterados = 0
            for rid in upd.index:
                o = orig.loc[rid] if rid in orig.index else None
                n = upd.loc[rid]
                # campos editáveis: status e hora_chegada
                status_changed = (o is None) or (o["status"] != n["status"])
                # hora_chegada pode vir NaN → vira None
                def _norm_min(v):
                    if v is None: return None
                    s = str(v)
                    if s == "nan": return None
                    try: return int(float(v))
                    except: return None
                h_old = _norm_min(None if o is None else o.get("hora_chegada"))
                h_new = _norm_min(n.get("hora_chegada"))
                hora_changed = (h_old != h_new)

                if status_changed or hora_changed:
                    try:
                        q_exec(
                            "update public.agenda set status=%s, hora_chegada=%s where id=%s",
                            (n["status"], h_new, int(rid)),
                        )
                        alterados += 1
                    except Exception as e:
                        st.error(f"Falha ao atualizar id {rid}: {e}")
            st.success(f"✅ {alterados} registro(s) atualizado(s)")
            # refresh do grupo
            try:
                # recarrega somente o grupo salvo
                rows = list_agenda_by_day(data_escolhida, eid)
                sub = [r for r in rows if r["entidade_id"] == eid]
                df = pd.DataFrame(sub)
                if not df.empty:
                    df.insert(1, "status_bolinha", df["status"].map(fmt_status_bolinha))
                    df.insert(3, "hora_fmt", df["hora_chegada"].apply(fmt_hhmm))
                    df = df.sort_values(["indice", "id"]).set_index("id", drop=True)
                    st.session_state["rows_agenda_groups"][eid]["orig"] = df.copy()
                    st.session_state["rows_agenda_groups"][eid]["edit"] = df.copy()
                else:
                    st.session_state["rows_agenda_groups"][eid]["orig"] = pd.DataFrame()
                    st.session_state["rows_agenda_groups"][eid]["edit"] = pd.DataFrame()
            except Exception as e:
                st.warning(f"Não foi possível recarregar o grupo {pack['nome']}: {e}")

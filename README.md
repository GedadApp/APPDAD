# GEDAD – Projeto de Teste (Multipáginas) – Agenda

Este pacote contém apenas a **página Agenda** em modo multipáginas, com:
- Pool de conexões (psycopg_pool)
- Paginação por cursor
- Índice automático via SQL (1..12 por entidade+data)
- Edição inline de `status` e `hora_chegada`
- Busca opcional de consulente em `leitores` (se a tabela existir)

## 🚀 Como rodar localmente

1. Crie um virtualenv e instale dependências:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Configure a conexão com o Postgres/Supabase:
   - Opção A (variável de ambiente):
     ```bash
     export DATABASE_URL="postgresql://usuario:senha@host:5432/base"
     ```
   - Opção B (arquivo `.streamlit/secrets.toml`):
     Preencha o campo `DATABASE_URL`.

3. (Opcional) Crie a tabela `agenda` para testes locais:
   - Execute o conteúdo de `sql/bootstrap_agenda.sql` no seu banco.

4. Rode o app:
   ```bash
   streamlit run app.py
   ```

## 📁 Estrutura

```
app.py
lib/
  __init__.py
  db.py
pages/
  1_Agenda.py
sql/
  bootstrap_agenda.sql
.streamlit/
  secrets.toml  # template
requirements.txt
```

## ℹ️ Notas
- A busca em `leitores` é opcional e só será usada se a tabela existir.
- Ajuste índices adicionais conforme o seu volume de dados.

- # Patch dual-mode + safe calls

1) Troque seu `lib/db.py` por este (dual-mode):
   - Por padrão usa pool (psycopg_pool).
   - Para desativar pool e usar conexão direta, defina no Streamlit Cloud (Secrets → Environment variables):
     USE_PG_POOL = "false"

2) Em `pages/1_Agenda.py`, envolva a chamada a `load_entidades()` no bloco SAFE CALL do arquivo:
   `pages_1_Agenda_safe_call_snippet.py`

3) Garanta que seu `DATABASE_URL` usa o host **pooler (porta 6543)** ou o **db (5432)**, ambos com:
   - `sslmode=require`
   - o patch já injeta `connect_timeout=8` e força IPv4 via `hostaddr=<ip>` automaticamente.

4) Se continuar com timeout no pool, rode em modo direto:
   - Adicione nos Secrets: `USE_PG_POOL = "false"`

5) Use o expander de **Teste de conexão** da página para validar.

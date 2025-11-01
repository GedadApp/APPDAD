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
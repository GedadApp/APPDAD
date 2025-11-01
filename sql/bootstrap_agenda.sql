-- Criação mínima para testes locais
create table if not exists agenda (
    id bigserial primary key,
    entidade text not null,
    data date not null,
    indice int not null check (indice between 1 and 12),
    consulente text,
    status text not null check (status in ('AGUARDANDO','AGENDADO','EM ATENDIMENTO','FINALIZADO')),
    hora_chegada time,
    criado_em timestamp without time zone default now()
);

create unique index if not exists agenda_unq_ent_data_ind on agenda (entidade, data, indice);
create index if not exists agenda_entidade_data_idx on agenda (entidade, data);
create index if not exists agenda_status_idx on agenda (status);
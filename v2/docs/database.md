# Banco de dados V2

## Papel

O banco local é o estado persistente administrado pelo SERM. Ele guarda metadados, relações, configurações, catálogo normalizado e estado operacional de scans.

**Não** é um armazenamento dos ROMs físicos.

## Stack

```text
Python
  ↓
SQLAlchemy 2.x + sqlite3 bootstrap
  ↓
SQLite
  ↑
versioned SQL migrations
```

O SQLAlchemy fornece a fronteira de engine usada pela aplicação; o bootstrap de migrations usa diretamente `sqlite3` para aplicar os arquivos SQL versionados. Alembic não faz parte do mecanismo atual.

As versões e dependências oficiais estão definidas em `pyproject.toml`.

## Estrutura

`serm_v2/database/` contém:

- `engine.py` — criação do engine SQLAlchemy;
- `bootstrap.py` — inicialização do banco e aplicação das migrations via SQLite;
- `models/` — modelos ORM quando aplicáveis;
- `migrations/` — evolução versionada do schema.

## Princípios

1. O schema V2 não replica o banco V1.
2. Cada mudança estrutural deve possuir migration.
3. Migrations publicadas são imutáveis.
4. Catálogos externos são normalizados antes de serem tratados como dados V2.
5. Caminhos físicos continuam referências para recursos externos.
6. Dados de scan devem ser persistíveis e reprocessáveis.
7. Cada migration possui um identificador numérico único.

## Migrations

As migrations são numeradas e aplicadas em ordem lexicográfica pelo bootstrap. A sequência atual é:

```text
001–012  configuração e catálogo MAME
013      mame_resolution_sources
014      rom_scan_schema
015      whloader_schema
016      mame_vsync_sources
017      scan_filter_pipeline
```

Não existem mais colisões de prefixos numéricos. Os identificadores antigos duplicados foram normalizados e não devem voltar a ser utilizados.

O bootstrap registra as versões em `schema_migrations` e possui tratamento especial para estruturas antigas do catálogo MAME.

## Integridade

Alterações de banco devem ser acompanhadas de:

- teste de bootstrap em banco limpo;
- teste de upgrade a partir do estado anterior relevante;
- verificação das constraints e índices;
- compatibilidade com os services que consomem o schema.

## Localização do banco

A arquitetura permite separar o estado do aplicativo do diretório de instalação e também suporta um modo portable. A política concreta de paths deve ser mantida no runtime/config, não espalhada pelos services.

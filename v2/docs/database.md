# Banco de dados V2

## Papel

O banco local é o estado persistente administrado pelo SERM. Ele guarda metadados, relações, configurações, catálogo normalizado e estado operacional de scans.

**Não** é um armazenamento dos ROMs físicos.

## Stack

```text
Python
  ↓
SQLAlchemy 2.x
  ↓
SQLite
  ↑
versioned SQL migrations
```

As versões e dependências oficiais estão definidas em `pyproject.toml`.

## Estrutura

`serm_v2/database/` contém:

- `engine.py` — criação/configuração do engine;
- `bootstrap.py` — inicialização do banco e aplicação das migrations;
- `models/` — modelos ORM quando aplicáveis;
- `migrations/` — evolução versionada do schema.

## Princípios

1. O schema V2 não replica o banco V1.
2. Cada mudança estrutural deve possuir migration.
3. Migrations aplicadas são imutáveis.
4. Catálogos externos são normalizados antes de serem tratados como dados V2.
5. Caminhos físicos continuam referências para recursos externos.
6. Dados de scan devem ser persistíveis e reprocessáveis.

## Migrations

As migrations são numeradas e devem ser aplicadas em ordem. A árvore atual contém migrations para configuração, localização, catálogo MAME, dados brutos, classificação, metadados, CHD/scan e pipelines auxiliares.

Há migrations com numeração histórica coincidente entre domínios diferentes. Antes de criar uma nova migration, deve-se verificar a sequência efetivamente existente no diretório para evitar colisões.

## Integridade

Alterações de banco devem ser acompanhadas de:

- teste de bootstrap em banco limpo;
- teste de upgrade a partir do estado anterior relevante;
- verificação das constraints e índices;
- compatibilidade com os services que consomem o schema.

## Localização do banco

A arquitetura permite separar o estado do aplicativo do diretório de instalação e também suporta um modo portable. A política concreta de paths deve ser mantida no runtime/config, não espalhada pelos services.

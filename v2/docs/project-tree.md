# SERM V2 — Estrutura do projeto

A V2 é um projeto Python independente dentro de `v2/`. A V1 é somente referência histórica e não participa da execução da V2.

## Árvore ativa

```text
v2/
├── README.md
├── pyproject.toml
├── .gitignore
├── .vscode/
│
├── docs/
│   ├── architecture-v2.md
│   ├── data-model-v2.md
│   ├── data-model-v2-detailed.md
│   ├── development-environment.md
│   ├── development-roadmap.md
│   ├── legacy-boundary.md
│   ├── launchbox-audit.md
│   ├── launchbox-provider.md
│   └── project-tree.md
│
├── data/                         # dados operacionais locais, NÃO versionados
│   ├── database/
│   ├── catalogs/
│   ├── cache/
│   ├── scans/
│   ├── staging/
│   ├── integrations/
│   ├── logs/
│   ├── exports/
│   └── backups/
│
├── serm_v2/
│   ├── config/
│   ├── database/
│   ├── domain/
│   ├── sources/
│   ├── catalog/
│   ├── library/
│   ├── emulation/
│   ├── reconstruction/
│   ├── runtime/
│   ├── integrations/
│   │   ├── launchbox.py
│   │   ├── launchbox_provider.py
│   │   └── launchbox_audit.py
│   └── gui/
│
└── tests/
```

## Política de dados

Durante o desenvolvimento, `data/` é a raiz operacional da V2. O mesmo modelo é usado em uma distribuição compilada: a raiz de dados fica ao lado do executável, salvo quando `SERM_DATA_DIR` for definido explicitamente.

```text
v2/data/
├── database/       → banco SQLite SERM
├── catalogs/       → catálogos importados
├── cache/          → dados descartáveis
├── scans/          → resultados de scans
├── staging/        → dados temporários de providers
├── integrations/   → configurações de integrações
├── logs/           → logs
├── exports/        → exportações geradas
└── backups/        → backups
```

A V2 não usa `%LOCALAPPDATA%\SERM` como localização padrão. Essa possibilidade pode ser fornecida futuramente por configuração explícita, mas a arquitetura atual privilegia dados pertencentes à instalação V2 e facilidade de portabilidade/backup.

## Regra de isolamento

Nenhum módulo V2 deve importar código, configuração ou banco da V1. Providers externos, como LaunchBox, também não são fonte de verdade: seus dados entram futuramente por adapters e normalizadores.

# SERM V2 — Árvore inicial

A V2 é um projeto Python independente dentro de `v2/`. A árvore foi organizada para facilitar o trabalho direto no Windows/VS Code e impedir que ferramentas de desenvolvimento descubram a V1 por acidente.

```text
v2/
├── README.md
├── pyproject.toml
├── .gitignore
├── .vscode/
│   ├── settings.json
│   ├── extensions.json
│   ├── launch.json
│   └── tasks.json
│
├── docs/
│   ├── architecture-v2.md
│   ├── data-model-v2.md
│   ├── data-model-v2-detailed.md
│   ├── development-environment.md
│   ├── development-roadmap.md
│   ├── legacy-boundary.md
│   └── project-tree.md
│
├── serm_v2/
│   ├── __init__.py
│   ├── __main__.py
│   ├── main.py
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py
│   │
│   ├── database/
│   │   ├── __init__.py
│   │   ├── engine.py
│   │   ├── models/
│   │   │   └── __init__.py
│   │   └── migrations/
│   │       └── README.md
│   │
│   ├── domain/
│   │   └── __init__.py
│   │
│   ├── sources/
│   │   ├── __init__.py
│   │   └── base.py
│   │
│   ├── catalog/
│   │   ├── __init__.py
│   │   └── service.py
│   │
│   ├── library/
│   │   └── __init__.py
│   │
│   ├── emulation/
│   │   └── __init__.py
│   │
│   ├── reconstruction/
│   │   └── __init__.py
│   │
│   ├── runtime/
│   │   ├── __init__.py
│   │   └── paths.py
│   │
│   ├── integrations/
│   │   └── launchbox.py
│   │
│   └── gui/
│       ├── __init__.py
│       ├── main_window.py
│       └── home.py
│
└── tests/
    ├── test_bootstrap.py
    └── test_launchbox.py
```

## LaunchBox

A integração inicial é deliberadamente pequena e independente do banco V2. Ela:

- descobre `LaunchBox.exe`;
- prioriza a instalação informada pelo usuário;
- inclui `G:\LaunchBox\LaunchBox.exe` entre os candidatos iniciais do ambiente atual;
- persiste somente o caminho do executável em `%LOCALAPPDATA%\SERM\integrations\launchbox.json`;
- abre o LaunchBox;
- localiza `Metadata\LaunchBox.Metadata.db`;
- localiza `Metadata\Platforms.xml`.

O banco do LaunchBox não é aberto nem copiado nesta etapa. Ele será consumido por um provider V2 depois que a Data Foundation estiver pronta.

## Diretórios que não pertencem ao Git

O projeto não deve criar um banco operacional dentro do checkout durante o uso normal. A política atual aponta os dados de usuário para:

```text
%LOCALAPPDATA%\SERM\
├── database\serm.db
├── catalogs\
├── cache\
├── scans\
├── staging\
├── integrations\
└── logs\
```

Um modo portable poderá futuramente usar um diretório local próprio, sem alterar a arquitetura do banco.

## Ferramentas de desenvolvimento

A configuração central está em `pyproject.toml`:

```text
pyproject.toml
├── build-system      → Hatchling
├── project           → metadados + runtime dependencies
├── optional dev      → pytest / coverage / Ruff
├── project.scripts   → comando `serm`
├── pytest             → descoberta e regras dos testes
├── coverage           → cobertura
└── ruff               → lint + format
```

O workspace VS Code fica dentro de `v2/.vscode/` para ser aplicado quando `v2/` for aberto como pasta do projeto.

## Regra de crescimento

Novos diretórios não devem ser criados apenas para acomodar código temporário. Cada novo pacote deve ter uma responsabilidade arquitetural definida e documentada.

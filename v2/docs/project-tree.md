# SERM V2 — Árvore inicial

```text
v2/
├── README.md
├── pyproject.toml
├── docs/
│   ├── architecture-v2.md
│   └── project-tree.md
├── serm_v2/
│   ├── __init__.py
│   ├── main.py
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py
│   ├── database/
│   │   ├── __init__.py
│   │   ├── engine.py
│   │   ├── models/
│   │   │   └── __init__.py
│   │   └── migrations/
│   │       └── README.md
│   ├── domain/
│   │   └── __init__.py
│   ├── sources/
│   │   ├── __init__.py
│   │   └── base.py
│   ├── catalog/
│   │   ├── __init__.py
│   │   └── service.py
│   ├── library/
│   │   └── __init__.py
│   ├── emulation/
│   │   └── __init__.py
│   ├── reconstruction/
│   │   └── __init__.py
│   ├── runtime/
│   │   ├── __init__.py
│   │   └── paths.py
│   └── gui/
│       ├── __init__.py
│       ├── main_window.py
│       └── home.py
└── tests/
    └── test_bootstrap.py
```

Essa árvore é deliberadamente pequena. Novos módulos só devem nascer quando houver responsabilidade definida no modelo V2.

Diretórios de dados de usuário não são versionados no Git:

```text
%LOCALAPPDATA%/SERM/
├── database/serm.db
├── catalogs/
├── cache/
├── scans/
├── staging/
└── logs/
```

Modo portable poderá futuramente usar `data/` ao lado do executável.

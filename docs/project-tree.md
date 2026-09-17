# Estrutura do projeto V2

A V2 é o projeto Python ativo do repositório. O workspace do VS Code aponta diretamente para `v2/`, enquanto a raiz do repositório mantém apenas arquivos de governança e o arquivo de workspace.

```text
SERM/
├── .github/
├── .gitignore
├── SERM.code-workspace
└── v2/
    ├── .editorconfig
    ├── .gitattributes
    ├── .gitignore
    ├── .vscode/
    │   ├── extensions.json
    │   ├── launch.json
    │   ├── settings.json
    │   └── tasks.json
    ├── LICENSE
    ├── README.md
    ├── config/
    │   └── mame/
    │       └── ui.ini
    ├── docs/
    ├── images/
    ├── pyproject.toml
    ├── serm_v2/
    │   ├── main.py
    │   ├── __main__.py
    │   ├── assets/
    │   ├── catalog/
    │   ├── config/
    │   ├── database/
    │   │   ├── bootstrap.py
    │   │   ├── engine.py
    │   │   ├── migrations/
    │   │   └── models/
    │   ├── domain/
    │   ├── emulation/
    │   ├── gui/
    │   ├── integrations/
    │   ├── library/
    │   ├── reconstruction/
    │   ├── runtime/
    │   ├── services/
    │   ├── sources/
    │   └── tools/
    └── tests/
```

## Governança da raiz

A raiz não deve conter código executável da V2. Ela contém apenas:

- `.github/` — configuração de integração do repositório;
- `.gitignore` — regras globais;
- `SERM.code-workspace` — abertura do projeto no VS Code.

A configuração específica do projeto foi movida para `v2/.vscode/`. Isso evita que configurações com caminhos relativos a V2 sejam interpretadas com a raiz do repositório como workspace.

## Configuração de desenvolvimento

`v2/.vscode/` é a configuração oficial do VS Code para a V2:

- `settings.json` — interpretador, pytest, Pylance e Ruff;
- `launch.json` — execução da aplicação e testes sob debugpy;
- `tasks.json` — instalação, execução, testes, cobertura, lint, formatação e validação;
- `extensions.json` — extensões recomendadas.

O `SERM.code-workspace` abre `v2/` como a pasta do workspace. Assim, `${workspaceFolder}` representa diretamente a raiz Python da V2.

## Dados e configurações externas

Arquivos de configuração de ferramentas externas que pertencem ao projeto devem ficar em `v2/config/<ferramenta>/`. O `ui.ini` do MAME foi colocado em `v2/config/mame/` porque não faz parte do pacote Python.

Dados de usuário, bancos locais, logs, caches, staging, exports e backups não pertencem à árvore versionada e são cobertos pelas regras de ignore.

## Pacote Python

`serm_v2/` é o único pacote de aplicação distribuído pelo `pyproject.toml`. Seus limites principais são:

- `gui/` — apresentação e interação Qt;
- `services/` — workflows e serviços de aplicação;
- `domain/` — conceitos de domínio;
- `database/` — persistência e migrations;
- `sources/` — contratos, routing e aquisição externa;
- `runtime/` — caminhos e ferramentas do ambiente;
- `integrations/` — integrações externas;
- `reconstruction/` — componentes de reconstrução;
- `emulation/` — componentes específicos de emulação;
- `tools/` — utilitários executáveis e auditorias;
- `assets/` — recursos empacotados.

## Migrations

As migrations usam sequência numérica única. A sequência atual termina em `017` e não deve possuir dois arquivos com o mesmo prefixo numérico. Cada migration deve registrar sua versão em `schema_migrations` quando aplicável e permanecer idempotente.

## Testes

`tests/` contém testes organizados por domínio. Novos serviços e migrations devem receber testes que cubram caminhos normais e falhas relevantes.

## Regra de dependência

Dependências preferenciais:

```text
GUI
 ↓
Services / Application workflows
 ↓
Domain + Sources + Database + Runtime
 ↓
Filesystem / SQLite / external tools
```

Evitar:

```text
GUI → SQL direto
GUI → varredura física complexa
GUI → parser específico de fonte
Service → código V1
Domain → GUI
```

## V1

A V1 não faz parte da árvore ativa atual do repositório. Caso material histórico da V1 seja reintroduzido, deverá permanecer isolado e não poderá ser importado pela V2.

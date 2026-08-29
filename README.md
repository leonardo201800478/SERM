# Strife Emulator and Roms Manager — SERM

**Produto:** Strife Emulator and Roms Manager (SERM)  
**Estado de referência:** 29/08/2026

## V2 é a linha ativa

O projeto entrou na **V2**, uma arquitetura nova e independente. A V1 permanece no repositório exclusivamente como referência histórica, fonte de aprendizado, comparação e pesquisa.

**V2 não depende da V1.** Não deve importar módulos, abrir o banco, ler configurações ou executar testes legados.

A nova base começa em `v2/` com uma Home limpa e uma arquitetura preparada para a Data Foundation.

```text
SERM/
├── .vscode/              # configuração do workspace principal
├── SERM.code-workspace   # workspace recomendado para o VS Code
├── v2/                   # projeto Python ativo
│   ├── serm_v2/
│   ├── tests/
│   ├── docs/
│   ├── data/
│   └── pyproject.toml
└── V1/                   # código histórico existente fora de v2/
```

## Desenvolvimento

O **workspace principal é a raiz `SERM/`**, mas todos os comandos Python da aplicação são executados dentro de `v2/`.

O `.vscode/settings.json` da raiz já aponta para:

```text
v2\.venv\Scripts\python.exe
```

e configura o terminal para iniciar em `v2/`. O VS Code também possui a configuração do ambiente Python V2. O comportamento segue a seleção de interpretador e ativação de ambientes suportadas pela extensão Python do VS Code. urlDocumentação Python do VS Codehttps://code.visualstudio.com/docs/languages/python

### Primeiro uso no clone

```powershell
cd .\v2
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### Validação oficial

A partir de `v2/`:

```powershell
python -m pytest
ruff check .
ruff format --check .
python -m serm_v2
```

A V2 possui seu próprio `pyproject.toml`, dependências, testes e configuração Ruff. A configuração no nível do repositório existe apenas para impedir que ferramentas executadas na raiz tratem a V1 como o projeto ativo. O Ruff permite configurar descoberta e exclusões pelo `pyproject.toml`. citeturn0search0

## Arquitetura de dados

SQLite será a fonte de verdade para dados administrados pelo SERM. ROMs, ISOs, CHDs e pacotes permanecem no filesystem.

```text
Source
 ↓
Catalog / Version
 ↓
Canonical Identity
 ↓
Mapping / Provenance
 ↓
File / Hash
 ↓
Scan / Transformation
 ↓
Execution Profile
```

Fontes de preservação continuam sendo referência factual. Fontes convenientes e metadata providers são integrados por adapters e DE-PARA.

## Fontes planejadas

### Preservação

- No-Intro / Dat-o-MATIC;
- Redump;
- MAME/listxml;
- FBNeo;
- MAME Softlists;
- fontes confiáveis de BIOS.

### Conveniência

- WHDLoad/Retroplay;
- eXoDOS;
- C64 Dreams/EasyFlash;
- fontes especializadas.

### Metadata

- RetroArch `.rdb`;
- LaunchBox `LaunchBox.Metadata.db`;
- LaunchBox `Platforms.xml`;
- LaunchBox `MAME.xml`;
- LaunchBox `Files.xml`;
- caches quando comprovadamente úteis.

## Configuração

O banco V2 armazenará configurações administradas pelo SERM. XML/CFG/JSON externos são formatos de interoperabilidade ou artefatos derivados quando necessários.

## V1 Legacy

O código histórico existente fora de `v2/` é mantido para pesquisa. Ele não define mais o contrato de desenvolvimento V2.

Consulte `v2/docs/legacy-boundary.md` para as regras da fronteira.

## Documentação V2

- `v2/README.md` — visão da nova linha;
- `v2/docs/architecture-v2.md` — arquitetura;
- `v2/docs/project-tree.md` — árvore inicial;
- `v2/docs/development-roadmap.md` — sequência de implementação;
- `v2/docs/development-environment.md` — ambiente de desenvolvimento;
- `v2/docs/legacy-boundary.md` — isolamento da V1;
- `docs/data-foundation.md` — decisões consolidadas de dados;
- `docs/source-strategy.md` — estratégia de fontes;
- `docs/catalogs.md` — catálogo;
- `docs/phases.md` — roadmap histórico/consolidado.

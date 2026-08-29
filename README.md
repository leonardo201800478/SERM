# Strife Emulator and Roms Manager — SERM

**Produto:** Strife Emulator and Roms Manager (SERM)  
**Estado de referência:** 29/08/2026

## V2 é a linha ativa

O projeto entrou na **V2**, uma arquitetura nova e independente. A V1 permanece no repositório exclusivamente como referência histórica, fonte de aprendizado, comparação e pesquisa.

**V2 não depende da V1.** Não deve importar módulos, abrir o banco, ler configurações ou executar testes legados.

A nova base começa em `v2/` com uma Home limpa e uma arquitetura preparada para a Data Foundation.

```text
v2/
├── serm_v2/
│   ├── gui/            # Home e interface V2
│   ├── database/       # SQLite + SQLAlchemy + migrations
│   ├── domain/         # entidades e regras
│   ├── sources/        # providers de dados
│   ├── catalog/        # catálogo e proveniência
│   ├── library/        # arquivos, hashes e scan
│   ├── emulation/      # runtime, emulator, core, profiles
│   ├── reconstruction/ # transformação e reconstrução
│   ├── runtime/        # paths e infraestrutura
│   └── config/         # configuração V2
├── tests/              # somente testes V2
└── docs/               # especificações V2
```

## V2 — arquitetura de dados

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

O código existente fora de `v2/` é mantido para pesquisa. Ele não define mais o contrato de desenvolvimento V2.

Consulte `v2/docs/legacy-boundary.md` para as regras da fronteira.

## Documentação V2

- `v2/README.md` — visão da nova linha;
- `v2/docs/architecture-v2.md` — arquitetura;
- `v2/docs/project-tree.md` — árvore inicial;
- `v2/docs/development-roadmap.md` — sequência de implementação;
- `docs/data-foundation.md` — decisões consolidadas de dados;
- `docs/source-strategy.md` — estratégia de fontes;
- `docs/catalogs.md` — catálogo;
- `docs/phases.md` — roadmap histórico/consolidado.

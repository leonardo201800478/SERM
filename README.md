# Strife Emulator and Roms Manager — SERM

**Nome do produto:** Strife Emulator and Roms Manager (SERM)  
**Repositório histórico:** `mame-set-builder`  
**Estado de referência:** 29/08/2026

O **SERM** é uma aplicação desktop Python/Qt para gerenciamento, auditoria, reconstrução e execução de bibliotecas de emulação. O projeto nasceu como MAME Set Builder e evoluiu para uma plataforma que separa dados, preservação, reconstrução, emuladores, RetroArch, controles, apresentação, downloads e integrações externas.

> **Fonte de verdade:** o código atual do repositório. A documentação distingue funcionalidade implementada, validada e planejada.

## Visão do produto

```text
                         SERM
                          │
       ┌──────────────────┼──────────────────┐
       │                  │                  │
   Data / Library      Execution        Presentation
       │                  │                  │
 Sources / Catalog    Emulators/Core    CRT / Shaders
 Identity / Scan      RetroArch         Overlays
 Rebuild / Mapping    Standalone        Controls
       │                  │                  │
       └──────────────────┼──────────────────┘
                          │
                    Integrations
```

## Princípio de dados

O SERM terá um banco SQLite próprio como fonte de verdade para os dados administrados pelo aplicativo. SQLAlchemy e migrations serão utilizados na camada Python.

```text
Source
 ↓
Catalog
 ↓
Canonical Identity
 ↓
Mapping / Provenance
 ↓
File / Hash
 ↓
Scan / Transformation
 ↓
Execution
```

Fontes oficiais/de preservação mantêm a referência factual. Fontes convenientes e providers de metadata podem ser associados por DE-PARA sem destruir a origem.

ROMs, ISOs, CHDs e pacotes permanecem no filesystem; o banco armazena metadata, hashes, relações, caminhos e estado.

## Núcleo MAME

```text
MAME listxml
    ↓
Dataset / SQLite
    ↓
Filtros
    ↓
Scan físico
    ↓
current_scan.jsonl
    ↓
Dependency Resolver
    ↓
Reconstrução MAME
    ↓
Set final / residual
```

FULLSET e origens são somente leitura. Machine é entidade lógica; arquivo é artefato físico. O Scan registra evidência física para reconstrução.

## Fontes

### Preservação / referência

- No-Intro / Dat-o-MATIC — cartuchos e mídias digitais suportadas;
- Redump — discos ópticos;
- MAME/listxml — arcade;
- FBNeo — arcade;
- MAME Softlists — sistemas suportados;
- fontes confiáveis para BIOS.

### Conveniência

- WHDLoad/Retroplay — Amiga;
- eXoDOS — MS-DOS;
- C64 Dreams/EasyFlash e fontes semelhantes;
- packs específicos.

### Metadata / integração

- RetroArch `.rdb`;
- LaunchBox `LaunchBox.Metadata.db`;
- LaunchBox `Platforms.xml`;
- LaunchBox `MAME.xml`;
- LaunchBox `Files.xml`;
- caches externos quando comprovadamente úteis.

O LaunchBox e o RetroArch são providers opcionais. O SERM não depende de suas instalações nem utiliza seus bancos como banco operacional.

## DE-PARA e nomenclatura

Uma fonte conveniente pode ser reorganizada para execução e scraping mantendo sua identidade de origem:

```text
Official Entry
      ↕
Identity Mapping
      ↕
Convenience Entry
      ↓
Transformation
      ↓
Execution Representation
```

O modelo pode distinguir:

```text
source_name
canonical_name
display_name
scraper_name
filename
normalized_name
```

WHDLoad/Retroplay e eXoDOS são casos prioritários dessa arquitetura.

## Reconstrução ampla

```text
Reconstrução
├── MAME
├── Consoles
│   ├── No-Intro
│   └── Redump
├── Amiga / WHDLoad / Retroplay
├── MS-DOS / eXoDOS
└── RetroArch BIOS
```

MAME e consoles não compartilham regras de catálogo. Compartilham somente infraestrutura genérica quando isso não compromete a semântica da fonte.

## Arquivos compactados

A infraestrutura comum é o `ArchiveService`:

```text
ArchiveService
├── ZIP → Python zipfile
├── 7Z  → 7z.exe preferencial / py7zr fallback
└── RAR → backend externo quando necessário
```

CHD permanece em serviço próprio.

## Emuladores

Backends standalone consolidados:

- MAME;
- Flycast;
- FBNeo;
- Supermodel.

RetroArch é tratado como runtime, com cores independentes.

A Home de RetroArch está concluída e validada, incluindo instalação/atualização do runtime, atualização de cores por CRC, retry de três tentativas por core, continuidade após falha, detecção de 7-Zip e fallback de extração.

## Configuração de execução

SQLite será a fonte de verdade das configurações administradas pelo SERM. XML/CFG/JSON externos serão formatos de interoperabilidade ou artefatos derivados quando necessários.

A configuração será modelada por plataforma/runtime/core/perfil. O SERM não deve armazenar cegamente uma configuração externa inteira como dependência do sistema.

## Apresentação / shaders

```text
Sistema
├── Core
├── Override
├── Shader
└── Overlay
```

Para RetroArch, priorizar shaders nativos leves e fiéis a CRT. Shaders de terceiros serão obtidos de seus repositórios de origem e não incorporados ao repositório do SERM. Aspect ratio representa o sistema/emulação, não o monitor.

## Controles e Force Feedback

Controles, hardware arcade e FFB permanecem domínios separados, com perfis por família/jogo e overrides específicos.

## Estado atual — 29/08/2026

### Concluído / validado

- núcleo MAME/listxml, SQLite, filtros e Scan;
- arquitetura estrutural de reconstrução MAME;
- arquitetura de emuladores e configuração;
- lazy loading das abas;
- consolidação Schema × Adapter dos emuladores;
- Home RetroArch;
- instalação/atualização RetroArch e cores;
- retry de download de cores: 3 tentativas por core e continuidade da fila;
- detecção de 7-Zip no Windows com fallback `py7zr`;
- infraestrutura inicial `ArchiveService`;
- testes consolidados da arquitetura atual;
- instalações reais validadas de MAME, Flycast, FBNeo e Supermodel;
- atualização automática da Home para estado READY após operações.

### Próxima macrofase

**Data Foundation + Source Manager + Catalog Foundation**

1. SQLite/SQLAlchemy/migrations definitivos;
2. diretórios de dados e paths;
3. Source Registry;
4. Catalog/CatalogVersion;
5. proveniência;
6. Platform/System/Canonical Identity;
7. DE-PARA;
8. File/Hash;
9. Runtime/Emulator/Core/ExecutionProfile;
10. Scan/Match/Transformation;
11. adapters locais LaunchBox e RetroArch para validar o modelo;
12. No-Intro;
13. Redump;
14. MAME/FBNeo/Softlists;
15. WHDLoad/Retroplay;
16. eXoDOS;
17. demais fontes.

### Depois

- reconstrução de consoles;
- reconstrução de discos/CHD;
- BIOS RetroArch;
- integração gradual do ArchiveService na reconstrução MAME;
- shaders/overlays por sistema;
- controles, hardware e FFB;
- downloads adicionais e aquisição/Torrent;
- integração/exportação LaunchBox.

## Regras de desenvolvimento

Antes de alterar código:

1. consultar o código atual no GitHub;
2. verificar modelos, schema e consumidores;
3. identificar funções ativas e legadas;
4. não remover funcionalidade ativa sem auditoria;
5. implementar em blocos pequenos;
6. executar testes da arquitetura atual;
7. validar fluxo real quando aplicável;
8. atualizar documentação somente com fatos verificados.

Documentação antiga não supera o código atual.

## Documentação principal

- `docs/architecture.md` — arquitetura geral;
- `docs/data-foundation.md` — banco, identidade, proveniência, configuração e modelo conceitual;
- `docs/source-strategy.md` — estratégia e autoridade das fontes;
- `docs/catalogs.md` — Catalog Manager;
- `docs/reconstruction.md` — reconstrução;
- `docs/reconstruction-consoles.md` — consoles;
- `docs/archives.md` — ArchiveService;
- `docs/chd-reconstruction.md` — CHD;
- `docs/retroarch.md` — RetroArch;
- `docs/phases.md` — roadmap;
- `mame-set-builder-Prompt MESTRE.md` — regras de evolução do projeto.

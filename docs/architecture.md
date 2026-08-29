# Arquitetura do SERM

**Produto:** Strife Emulator and Roms Manager (SERM)  
**Repositório histórico:** `mame-set-builder`  
**Referência:** 29/08/2026

## 1. Princípio arquitetural

O SERM é dividido em domínios de dados, catálogo, preservação, reconstrução, execução, apresentação, hardware, downloads e integrações.

```text
GUI / Qt
   ↓
Application Services
   ↓
Domain
├── Data Foundation / Database
├── Source Manager / Catalog
├── Identity / Mapping
├── Library / Dataset / Scan
├── Reconstruction
│   ├── MAME
│   ├── Consoles / No-Intro
│   ├── Discs / Redump
│   ├── Amiga / WHDLoad / Retroplay
│   └── MS-DOS / eXoDOS
├── RetroArch BIOS
├── Emulator / Backend / Core
├── Archive / Package
├── Controls / Hardware / FFB
├── Presentation / Shader / Overlay
└── External Integrations
```

A GUI coordena. Regras de negócio e I/O pesado permanecem em services/workers.

## 2. Data Foundation

O banco local principal será SQLite, acessado por Python via SQLAlchemy e migrations versionadas.

```text
serm.db
├── Sources / Catalogs
├── Identity / Releases
├── Platforms / Systems
├── Files / Hashes
├── Archives / Discs / BIOS
├── Runtime / Emulator / Core
├── Execution Profiles / Paths
├── Scan
└── Mapping / Transformation
```

O banco guarda metadata, relações e estado. ROMs, ISOs, CHDs e pacotes permanecem no filesystem.

O banco não deve ficar obrigatoriamente no diretório de instalação. A arquitetura deve suportar `%LOCALAPPDATA%/SERM/` e modo portable.

### Source ≠ Catalog ≠ Identity ≠ File

```text
Source
 ↓
CatalogVersion
 ↓
CatalogEntry
 ↓
CanonicalIdentity
 ↓
File / Hash
```

A fonte oficial aplicável mantém a referência factual. Fontes convenientes e metadata providers são relacionados por adapters e mapping.

## 3. Fontes e autoridade

### Preservação / referência

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
- packs específicos.

### Metadata / integração

- RetroArch `.rdb`;
- LaunchBox `LaunchBox.Metadata.db`;
- LaunchBox `Platforms.xml`;
- LaunchBox `MAME.xml`;
- LaunchBox `Files.xml`;
- caches externos quando comprovadamente úteis.

Nenhum metadata provider se torna fonte de verdade física apenas por ser importado.

## 4. Identity e DE-PARA

```text
Official Entry
      ↕
Identity Mapping
      ↕
Convenience Entry
```

O mapping registra origem, destino, tipo, confiança, evidências, regra, versão e data quando aplicável.

O modelo de nomes deve distinguir, quando necessário:

```text
source_name
canonical_name
display_name
scraper_name
filename
normalized_name
```

Isso permite reorganizar WHDLoad/eXoDOS para execução e scraping sem perder a nomenclatura de origem.

## 5. Plataformas e execução

`Platform` é entidade do SERM. Não é sinônimo de emulador, runtime, core ou fabricante.

```text
Runtime
  └── Emulator / Backend
        └── Core (quando aplicável)
              ↓
        ExecutionProfile
              ↓
          Platform
```

O ExecutionProfile poderá armazenar propriedades conhecidas de execução, incluindo argumentos, extensões, BIOS, shaders, overlays e paths.

SQLite será a fonte de verdade das configurações administradas pelo SERM. XML/CFG/JSON externos serão formatos de interoperabilidade/artefatos derivados quando necessários.

## 6. LaunchBox como referência e provider

A análise do `LaunchBox.Metadata.db` mostrou estruturas úteis:

```text
Games
Platforms
Emulators
EmulatorPlatforms
GameAlternateTitles
GameImages
```

O LaunchBox usa SQLite e Entity Framework migrations. O SERM não copiará o schema nem dependerá do LaunchBox.

O `Platforms.xml` é fonte adicional de metadata técnica/classificação, incluindo `Category`, `Emulated` e `UseMameFiles`. Registros explicitamente obsoletos/duplicados não devem ser importados cegamente.

O LaunchBox será provider de metadata, nomes, plataformas, IDs e relações úteis. O SERM manterá sua própria identidade e banco.

## 7. RetroArch RDB

`.rdb` é provider local de metadata/identificação. Pode auxiliar matching por hash/nome e associação com sistemas/core, mas não substitui No-Intro, Redump ou MAME quando aplicáveis.

## 8. Núcleo MAME

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
Set / residual
```

FULLSET e origens são somente leitura. O Scan fornece evidência física. Nenhuma camada de execução altera a identidade física do conteúdo.

## 9. Reconstrução

A reconstrução é um domínio comum com adapters por fonte. Hash matching, planejamento, staging, publicação atômica e validação podem ser compartilhados; a semântica de cada fonte não.

### No-Intro

Cartuchos/mídias digitais suportadas. Preservar nome, parent/clone, ROM, tamanho, CRC32, MD5, SHA1 e demais metadados do DAT.

### Redump

Discos e faixas. CHD é saída preferencial quando tecnicamente compatível; ISO/BIN-CUE podem ser intermediários.

### Amiga

WHDLoad/Retroplay é fonte conveniente especializada. Pacotes, versões e variantes serão mapeados para identidade canônica e classificados por sistema/compatibilidade. Não modelar WHDLoad como No-Intro.

### MS-DOS

eXoDOS é fonte conveniente. Quando compatível, preservar e executar o `.zip` diretamente com DOSBox-Pure, standalone ou core, evitando transformação desnecessária.

## 10. ArchiveService

```text
ArchiveService
├── ZIP → Python zipfile
├── 7Z  → 7z.exe preferencial / py7zr fallback
└── RAR → backend externo quando necessário
```

Responsabilidades: detectar, listar, testar, extrair, criar, editar quando necessário, temporários seguros e publicação atômica. CHD possui serviço próprio.

## 11. Hash matching

A infraestrutura deve suportar SHA-1, MD5, CRC32, SHA-256 e outros algoritmos quando necessários. Nome não é identidade física primária.

## 12. RetroArch

RetroArch é runtime com cores Libretro, system, assets, saves, states, shaders e configuração própria. A Home está concluída e validada em fluxo real.

Configurações nativas válidas devem ser preservadas. O SERM altera somente propriedades conhecidas e suportadas.

## 13. Presentation

```text
Sistema
├── Core
├── Override
├── Shader
└── Overlay
```

Shaders de terceiros vêm de seus repositórios de origem. CRT limpo e leve é prioridade. A proporção representa o sistema/emulação; não forçar 16:9 por causa do monitor.

## 14. Scan, transformação e segurança

```text
Source/Catalog
 ↓
Scan / Match
 ↓
Mapping
 ↓
Transformation / Reconstruction
 ↓
Staging
 ↓
Validation
 ↓
Atomic Publish
```

Regras:

- origens somente leitura;
- staging temporário;
- hashes antes da publicação;
- proteção contra path traversal;
- nenhum arquivo parcial publicado;
- nenhum cache permanente de ROMs por causa do catálogo;
- não executar conteúdo baixado como parte da validação;
- registrar falhas de forma acionável.

## 15. Testes

A suíte cobre a arquitetura atual. Testes legados de código removido devem ser eliminados.

Cada fase relevante exige unitários, integração, fixtures reais quando possível, falhas/interrupção, filesystem e fluxo real quando houver runtime/download.

## 16. Referências internas

- `docs/data-foundation.md` — banco, identidade, configuração, proveniência e modelo conceitual;
- `docs/source-strategy.md` — classificação e estratégia de fontes;
- `docs/catalogs.md` — Catalog Manager;
- `docs/reconstruction.md` — reconstrução;
- `docs/reconstruction-consoles.md` — consoles;
- `docs/archives.md` — ArchiveService;
- `docs/chd-reconstruction.md` — CHD;
- `docs/retroarch.md` — RetroArch;
- `docs/phases.md` — roadmap.

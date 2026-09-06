# Data Foundation — SERM

**Referência:** 29/08/2026  
**Status:** arquitetura consolidada; implementação pendente

## 1. Objetivo

A Data Foundation é a camada persistente comum do SERM. Deve sustentar fontes, catálogos, identidade, hashes, arquivos, plataformas, runtimes, cores, perfis de execução, paths, scan, mapeamentos DE-PARA e transformações.

Princípio central:

> A fonte de preservação mantém a referência factual; fontes convenientes e fontes de metadata podem enriquecer ou fornecer uma representação operacional por meio de mapeamentos explícitos.

Nenhuma fonte externa deve substituir silenciosamente outra fonte de maior autoridade.

## 2. Banco de dados

O banco local principal será **SQLite**, acessado pelo Python por **SQLAlchemy** e migrations versionadas.

SQLite foi escolhido por ser adequado ao aplicativo desktop: não exige servidor, é transacional, portátil, simples de distribuir e permite índices, views, triggers e FTS5.

O banco não armazenará ROMs/ISOs/CHDs completos. O conteúdo permanece no filesystem; o banco armazena metadata, hashes, caminhos, relações e estado.

### Localização

A arquitetura deve suportar instalação normal e modo portable:

```text
Instalação normal
Program Files/SERM/
        ↓
%LOCALAPPDATA%/SERM/

Portable
SERM/
├── SERM.exe
└── data/
```

O caminho deve ser resolvido por uma camada própria de configuração de dados, nunca codificado no domínio.

## 3. Princípios de modelagem

### Source ≠ Catalog ≠ Identity ≠ File

```text
Source
  ↓
Catalog / CatalogVersion
  ↓
CatalogEntry
  ↓
CanonicalIdentity
  ↓
File / Hash
```

Nome de arquivo não é identidade física. A identidade física deve usar a evidência disponível da fonte, especialmente hash e tamanho.

### Proveniência

Informações relevantes importadas devem conservar sua origem quando necessário para auditoria e resolução de conflitos.

### Hashes

Hashes serão dados estruturados e extensíveis. Devem suportar pelo menos SHA-1, MD5, CRC32 e SHA-256 quando aplicável. A prioridade do matching depende da fonte e da evidência disponível.

## 4. Modelo conceitual

O schema será construído progressivamente. Entidades previstas:

```text
sources
source_versions
source_files
catalogs
catalog_versions
catalog_entries

platforms
platform_aliases
systems

canonical_entities
canonical_releases
source_entry_mappings

files
file_hashes
archives
archive_members
discs
disc_tracks
bios
bios_files

runtimes
emulators
cores
execution_profiles
execution_platforms
paths

scan_runs
scan_files
scan_matches

transformations
transformation_rules
transformation_jobs
transformation_results
```

Os nomes são conceituais e não constituem ainda o schema SQL definitivo.

## 5. Platform

`Platform` será uma entidade própria do SERM. Não deve ser confundida com fabricante, hardware físico, emulador, runtime, core ou categoria de front-end.

Uma plataforma pode possuir metadata técnica, aliases e relações com múltiplos runtimes/cores.

## 6. Runtime, Emulator e Core

```text
Runtime
  └── Emulator / Backend
        └── Core (quando aplicável)
```

RetroArch é runtime e executa cores Libretro. MAME, Flycast, FBNeo e Supermodel podem possuir backends standalone.

`ExecutionProfile` relacionará plataforma, runtime/backend, core quando aplicável, argumentos, extensões, BIOS, shaders, overlays e demais propriedades administradas pelo SERM.

## 7. Configuração

O SQLite será a fonte de verdade para as configurações administradas pelo SERM.

XML/CFG/JSON de aplicações externas serão formatos de interoperabilidade ou artefatos derivados quando necessários.

O SERM não deve armazenar cegamente uma configuração externa inteira como blob obrigatório. Deve modelar as propriedades conhecidas e usar adapters para gerar/aplicar o formato externo.

Configurações nativas válidas devem ser preservadas; alterações ficam limitadas às propriedades suportadas e seguem backup/rollback.

## 8. DE-PARA e Identity Mapping

Fontes convenientes não substituem fontes oficiais.

```text
Official Catalog Entry
          ↕
   Identity Mapping
          ↕
Convenience Catalog Entry
```

O mapping deverá registrar origem, destino, tipo, confiança, evidências, regras, versão da fonte e data da resolução.

Isso permite, por exemplo, relacionar um pacote WHDLoad/Retroplay ou eXoDOS à identidade canônica do SERM sem perder o nome e a estrutura originais da fonte.

## 9. Transformações

Transformação é um domínio separado de fonte e catálogo. Tipos previstos incluem:

```text
rename
move
extract
repack
merge
split
reconstruct
convert
```

Cada transformação deve registrar origem, destino, regra e resultado para permitir auditoria e reprodução.

## 10. Fontes de preservação

Principais fontes planejadas:

- No-Intro / Dat-o-MATIC para cartuchos e mídias digitais suportadas;
- Redump para discos ópticos;
- MAME/listxml para arcade;
- FBNeo e suas fontes específicas;
- MAME Softlists quando aplicável;
- fontes próprias/confiáveis para BIOS.

Cada fonte possui semântica própria. O SERM compartilha infraestrutura apenas onde isso não destrói a semântica da fonte.

## 11. Fontes convenientes

Fontes convenientes são suportadas sem se tornarem a autoridade de preservação:

- WHDLoad/Retroplay para Amiga;
- eXoDOS para MS-DOS;
- C64 Dreams/EasyFlash e outras coleções quando aplicável;
- packs comunitários e outras fontes específicas.

O SERM pode reorganizar, renomear, separar, transformar ou preparar essas fontes para execução, mantendo a proveniência e o DE-PARA.

### Exemplo Amiga

```text
WHDLoad / Retroplay
        ↓
identificação / mapping
        ↓
Canonical Game
        ↓
classificação por sistema/compatibilidade
        ↓
nome canônico para scraper
        ↓
pacote pronto para execução
```

O arquivo original e seu nome permanecem registrados como dados de origem.

### Exemplo MS-DOS

```text
eXoDOS
   ↓
Source Adapter
   ↓
Canonical Identity
   ↓
DE-PARA
   ↓
ZIP preservado quando compatível
   ↓
DOSBox-Pure standalone/core
```

O objetivo é evitar extração/reempacotamento desnecessário quando o runtime suporta diretamente a representação existente.

## 12. Metadata Providers

O SERM poderá importar metadata de:

- RetroArch `.rdb`;
- LaunchBox `LaunchBox.Metadata.db`;
- LaunchBox `MAME.xml`;
- LaunchBox `Platforms.xml`;
- LaunchBox `Files.xml`;
- caches externos quando forem úteis e identificados como cache.

Essas fontes são providers de metadata/identificação/enriquecimento e não substituem automaticamente fontes de preservação.

## 13. LaunchBox como referência

A análise do `LaunchBox.Metadata.db` mostrou estruturas úteis:

```text
Games
Platforms
Emulators
EmulatorPlatforms
GameAlternateTitles
GameImages
```

O LaunchBox também utiliza SQLite e Entity Framework migrations.

O SERM **não copiará o schema do LaunchBox**. Aproveitará os conceitos úteis e terá um modelo próprio orientado a preservação, identidade, proveniência e reconstrução.

Diferenças deliberadas:

- foreign keys reais quando apropriado;
- identidade canônica independente da fonte;
- releases independentes da simples coluna textual de plataforma;
- hashes estruturados;
- proveniência explícita;
- runtime/core separados;
- DE-PARA e transformação como domínios próprios.

## 14. LaunchBox Platforms.xml

O `Platforms.xml` é uma fonte relevante para normalização e enriquecimento de plataformas. Campos como `Emulated`, `Category` e `UseMameFiles` são úteis para classificação e relacionamento com o ecossistema MAME.

Registros explicitamente obsoletos, duplicados ou marcados para remoção no próprio XML não devem ser importados cegamente.

O nome canônico do SERM permanece independente do LaunchBox.

## 15. RetroArch RDB

Os `.rdb` da pasta `database` do RetroArch serão tratados como fonte de metadata/identificação auxiliar.

```text
arquivo físico
 ↓
hash / metadata
 ↓
RetroArch RDB
 ↓
identificação auxiliar
 ↓
Canonical Identity
```

Quando houver No-Intro, Redump ou outra fonte de preservação aplicável, o RDB não a substitui.

## 16. Atualização e staging

Fontes externas seguem:

```text
Download
 ↓
Validation
 ↓
Parse
 ↓
Normalize
 ↓
Transaction
 ↓
Publish
```

Falha de download, validação ou parsing não pode destruir a versão local válida.

Registrar provider, versão/data, origem, integridade quando disponível, data da sincronização e parser/schema utilizado.

Catálogo local não é cache de ROMs.

## 17. Integridade e concorrência

A implementação deve considerar:

- SQLite WAL quando adequado;
- foreign keys habilitadas;
- migrations versionadas;
- transações curtas e explícitas;
- índices derivados de consultas reais;
- operações pesadas fora da GUI;
- nenhuma publicação parcial;
- recuperação após interrupção.

## 18. Ordem de implementação

### Fase 1 — Fundação

1. diretórios de dados;
2. SQLite;
3. SQLAlchemy;
4. migrations;
5. conexão/session;
6. foreign keys;
7. logging de banco;
8. schema inicial mínimo;
9. testes de migration/rollback.

### Fase 2 — Source Registry

1. Source;
2. SourceVersion;
3. SourceFile;
4. Catalog;
5. CatalogVersion;
6. staging e integridade.

### Fase 3 — Identity e Platform

1. Platform;
2. aliases;
3. System;
4. CanonicalEntity;
5. releases;
6. source identity/mapping.

### Fase 4 — File/Hash

1. File;
2. FileHash;
3. Archive;
4. ArchiveMember;
5. Disc/Track;
6. BIOS.

### Fase 5 — Execution

1. Runtime;
2. Emulator/Backend;
3. Core;
4. ExecutionProfile;
5. Paths.

### Fase 6 — Scan/Transformation

1. ScanRun;
2. ScanFile;
3. Match;
4. Transformation;
5. jobs/results.

Somente depois os providers completos devem alimentar o modelo definitivo.

## 19. Critério de conclusão

A Data Foundation estará concluída quando:

- o banco iniciar por migration limpa;
- a aplicação inicializar sem intervenção manual;
- migrations forem testadas;
- integridade referencial estiver ativa;
- paths forem independentes do diretório do executável;
- uma fonte puder ser registrada e versionada;
- uma identidade puder ser relacionada a múltiplas fontes;
- hashes forem extensíveis;
- configuração de execução puder ser persistida sem depender de XML;
- nenhum fluxo MAME válido for quebrado.

# Roadmap do SERM

**Produto:** Strife Emulator and Roms Manager (SERM)  
**Repositório histórico:** `mame-set-builder`  
**Estado de referência:** 29/08/2026

## Fases concluídas / consolidadas

### 1 — Dataset MAME e filtros

- MAME/listxml;
- parser/modelos;
- SQLite/migrations existentes;
- classificação e filtros;
- XML filtrado.

### 2 — Scan físico

- Scan ROMs;
- diagnóstico físico;
- estados de integridade;
- `current_scan.jsonl`;
- origem física.

### 3 — Base de reconstrução MAME

A arquitetura estrutural está definida para ROMs, dependências e staging, mantendo origens somente leitura.

### 4 — Plataforma de emuladores

MAME, Flycast, FBNeo e Supermodel possuem infraestrutura de runtime/configuração consolidada e validada em fluxos reais de instalação.

### 5 — RetroArch Home e atualização de cores

Concluída a Home, com lazy loading e ciclo READY após operações. O fluxo real de cores usa índice oficial, comparação CRC, retry de três tentativas por core e continuidade da fila após falha.

### 6 — ArchiveService inicial

Infraestrutura comum para ZIP/7Z, com 7-Zip externo preferencial no Windows e `py7zr` como fallback. A criação de ZIP é atômica e possui validação.

## Próxima macrofase — Data Foundation e Source Manager

A próxima etapa não começa por um novo reconstrutor específico. Primeiro será consolidada a base de dados comum que permitirá integrar fontes de preservação, fontes convenientes e providers de metadata sem acoplamento.

```text
Data Foundation
      ↓
Source Registry / Providers
      ↓
Catalog Manager
      ↓
Canonical Identity + DE-PARA
      ↓
Scan / Matching
      ↓
Transformation / Reconstruction
      ↓
Execution
```

### Fase A — Data Foundation

**Prioridade: máxima**

1. definir diretórios de dados;
2. SQLite como banco local principal;
3. SQLAlchemy;
4. migrations versionadas;
5. conexão/session;
6. foreign keys;
7. logging de banco;
8. schema inicial mínimo;
9. testes de migration/rollback;
10. paths independentes do diretório do executável.

O banco guarda metadata/estado e referências; ROMs, ISOs, CHDs e pacotes permanecem no filesystem.

### Fase B — Source Registry e Catalog Foundation

1. Source;
2. SourceVersion;
3. SourceFile;
4. Catalog;
5. CatalogVersion;
6. staging;
7. validação;
8. ativação/rollback;
9. proveniência;
10. base para providers locais e remotos.

### Fase C — Identity, Platform e DE-PARA

1. Platform;
2. aliases;
3. System;
4. CanonicalEntity;
5. Release;
6. source identity;
7. source-entry mapping;
8. nomes source/canonical/display/scraper/filename/normalized;
9. resolução de conflitos e confiança.

### Fase D — Runtime e configuração

1. Runtime;
2. Emulator/Backend;
3. Core;
4. ExecutionProfile;
5. Platform × Runtime/Core;
6. Paths;
7. propriedades de configuração administradas pelo SERM;
8. adapters para XML/CFG/JSON externos quando necessários.

SQLite será a fonte de verdade das configurações administradas pelo SERM. Arquivos externos serão formatos derivados/interoperabilidade quando aplicável.

### Fase E — File, Hash e Scan

1. File;
2. FileHash;
3. Archive;
4. ArchiveMember;
5. Disc/Track;
6. BIOS;
7. ScanRun;
8. ScanFile;
9. ScanMatch.

### Fase F — Providers de referência e metadata

Ordem inicial:

1. LaunchBox `Metadata.db` / `Platforms.xml` como providers locais para validar Platform, Game, Emulator e metadata;
2. RetroArch `.rdb` como provider local de identificação/metadata;
3. No-Intro;
4. Redump;
5. MAME/listxml integrado ao dataset existente;
6. FBNeo;
7. MAME Softlists;
8. demais fontes especializadas.

LaunchBox e RetroArch são usados cedo para validar o modelo, mas não se tornam fontes de verdade física.

### Fase G — Catalog Manager completo

1. No-Intro provider/parser;
2. fixture Mega Drive/Genesis;
3. sincronização e rollback;
4. Redump provider após validar endpoints/arquivos atuais;
5. Amiga/Retroplay;
6. eXoDOS;
7. demais providers.

O Catalog Manager não baixa ROMs automaticamente.

### Fase H — Reconstrução por domínio

#### No-Intro

1. `NoIntroGame` / `NoIntroRom`;
2. Parent/Clone;
3. hash matching;
4. Reconstruction Planner;
5. ZIP Builder via ArchiveService;
6. validação contra DAT;
7. residual/pendências;
8. GUI Consoles.

#### Redump

1. `RedumpDisc`;
2. catálogo/versionamento;
3. matching;
4. modelo de imagem/faixas;
5. CUE/BIN/ISO e demais formatos necessários;
6. CHD Builder;
7. validação;
8. CHD como saída preferencial quando compatível.

#### Amiga / WHDLoad / Retroplay

1. catálogo;
2. pacote/versão/variante;
3. mapping para identidade canônica;
4. organização por sistema/compatibilidade;
5. nomenclatura adequada para scraper;
6. suporte LHA/LZX quando implementado;
7. validação.

#### MS-DOS / eXoDOS

1. catálogo/metadata;
2. identidade;
3. mapping;
4. preservação de pacotes quando compatível;
5. execução direta por DOSBox-Pure quando suportada;
6. standalone/core;
7. validação.

### Fase I — RetroArch BIOS

1. catálogo derivado de `.info`/fontes confiáveis;
2. scanner;
3. hash matching;
4. classificação OK/renomeável/movível/reconstruível/MISSING;
5. reconstrução/instalação somente do necessário;
6. testes reais.

### Fase J — Integração do ArchiveService

Migrar consumidores gradualmente:

1. RetroArch;
2. shaders/pacotes;
3. reconstrução MAME;
4. demais downloads;
5. remover duplicações somente após cobertura de testes.

## Fases posteriores

### Presentation / CRT

- Shader/Override/Overlay por sistema;
- shaders RetroArch;
- shaders de terceiros via repositórios de origem;
- CRT limpo e leve;
- compatibilidade por renderer;
- sem forçar 16:9 do monitor sobre o sistema.

### Controles / Hardware / FFB

- Control Profiles;
- Control Families;
- Hardware Profiles;
- Arcade Hardware Profiles;
- volante/pedais/câmbio;
- FFB por família/jogo.

### Downloads / aquisição

- providers adicionais;
- validação;
- staging;
- backup/rollback;
- qBittorrent/Torrent em fase futura.

### LaunchBox integration

- importação de metadata;
- exportação incremental;
- XML derivado quando necessário;
- categorias e plataformas;
- preservação do conteúdo externo;
- LaunchBox não é dependência do SERM.

## Qualidade

Cada macrofase exige:

- testes somente da arquitetura atual;
- remoção de testes legados quando o código correspondente não existir mais;
- fixtures reais quando possível;
- testes de falha/interrupção;
- validação real de download e filesystem;
- medição de CPU, memória e I/O em operações intensivas.

## Regra de conclusão

Uma fase só é concluída quando o fluxo real correspondente estiver implementado e testado. Modelos, placeholders, telas vazias ou documentação não equivalem a funcionalidade concluída.

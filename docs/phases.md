# Roadmap do SERM

**Produto:** Strife Emulator and Roms Manager (SERM)
**Repositório histórico:** `mame-set-builder`
**Estado de referência:** 29/08/2026

## Fases concluídas / consolidadas

### 1 — Dataset MAME e filtros

- MAME/listxml;
- parser/modelos;
- SQLite/migrations;
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

Concluída a Home, com lazy loading e ciclo READY após operações. O fluxo real de cores usa índice oficial, comparação CRC, seleção somente dos desatualizados, retry de três tentativas por core e continuidade da fila após falha.

### 6 — ArchiveService inicial

Infraestrutura comum para ZIP/7Z, com 7-Zip externo preferencial no Windows e `py7zr` como fallback. A criação de ZIP é atômica e possui validação.

## Próxima macrofase — Reconstrução ampla

A reconstrução deixa de ser tratada como somente MAME:

```text
Reconstrução
├── MAME
├── Consoles
│   ├── No-Intro
│   ├── Redump
│   └── Amiga / WHDLoad / Retroplay
└── RetroArch BIOS
```

### Fase A — Catalog Manager

**Prioridade: máxima**

1. `CatalogProvider` comum;
2. cache/versionamento de catálogos;
3. atualização automática;
4. validação antes de substituir catálogo local;
5. No-Intro provider;
6. parser DAT/XML;
7. fixture Mega Drive/Genesis fornecida;
8. testes de sincronização;
9. Redump provider após validar seus arquivos/endpoints atuais;
10. Amiga/Retroplay provider.

O Catalog Manager baixa metadados de referência, não ROMs.

### Fase B — No-Intro Console Reconstruction

1. `NoIntroGame` / `NoIntroRom`;
2. Parent/Clone explícito;
3. hash matching;
4. scanner integrado;
5. Reconstruction Planner;
6. ZIP Builder via ArchiveService;
7. validação contra DAT;
8. residual/pendências;
9. fixtures reais;
10. GUI Consoles.

### Fase C — Redump / Disc Reconstruction

1. `RedumpDisc`;
2. catálogo/versionamento;
3. matching por hashes/metadados;
4. modelos de imagem;
5. CUE/BIN/ISO e demais fontes necessárias;
6. CHD Builder;
7. validação CHD;
8. CHD como saída padrão quando compatível;
9. fixtures de discos com múltiplas faixas;
10. GUI de discos.

### Fase D — Amiga / WHDLoad / Retroplay

1. catálogo;
2. versão/variante;
3. modelo `AmigaPackage`;
4. fontes e downloads;
5. suporte explícito a LHA/LZX quando implementado;
6. matching/instalação;
7. validação.

### Fase E — RetroArch BIOS

1. catálogo derivado de `.info`/fontes confiáveis;
2. scanner rápido;
3. hash matching;
4. classificação OK/renomeável/movível/reconstruível/MISSING;
5. reconstrução/instalação somente do necessário;
6. testes reais com BIOS de sistemas relevantes.

### Fase F — Integração do ArchiveService

Migrar gradualmente os consumidores existentes, sem substituir código funcional de forma cega:

1. RetroArch;
2. shaders/pacotes;
3. reconstrução MAME;
4. demais downloads;
5. remover implementações duplicadas somente após cobertura de testes.

## Fases posteriores

### Emuladores / execução

- RetroArch como backend completo;
- seleção de core;
- assets/system/saves/states;
- configuração por runtime.

### Presentation / CRT

- Shader/Override/Overlay por sistema;
- shaders RetroArch;
- shaders de terceiros via download dos repositórios de origem;
- CRT limpo e leve como prioridade;
- compatibilidade por renderer;
- sem forçar aspect ratio 16:9 do monitor sobre o sistema.

### Controles / Hardware / FFB

- Control Profiles;
- Control Families;
- Hardware Profiles;
- Arcade Hardware Profiles;
- G27/volante/pedais/câmbio;
- FFBArcadePlugin;
- FFB por família/jogo.

### Downloads / aquisição

- providers adicionais;
- validação;
- staging;
- backup/rollback;
- qBittorrent/Torrent em fase futura.

### LaunchBox

- exportação incremental;
- XML derivado;
- categorias e plataformas;
- preservação do conteúdo externo.

## Qualidade

Cada macrofase exige:

- testes somente da arquitetura atual;
- remoção de testes legados quando o código correspondente não existir mais;
- fixtures reais quando possível;
- testes de falha/interrupção;
- validação real de download e filesystem;
- medição de CPU, memória e I/O quando houver operações intensivas.

## Regra de conclusão

Uma fase só é concluída quando o fluxo real correspondente estiver implementado e testado. Modelos, placeholders, telas vazias ou documentação não equivalem a funcionalidade concluída.
